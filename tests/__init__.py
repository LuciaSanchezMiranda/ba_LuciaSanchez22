"""Pruebas de AP7. Ejecutar: python -m unittest tests -v."""

import json
from decimal import Decimal
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import Mock, patch

from flask import Flask

from app.repositories.sqlserver.sales_repository import SalesRepository
from app.routes.sales_routes import sales_bp


class SalesTotalTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.register_blueprint(sales_bp)
        self.client = self.app.test_client()

    @staticmethod
    def fixture_connection():
        # Base temporal de prueba: nunca escribe en SQL Server ni en datos reales.
        connection = sqlite3.connect(':memory:')
        connection.create_function('YEAR', 1, lambda value: int(value[:4]))
        connection.create_function('MONTH', 1, lambda value: int(value[5:7]))
        connection.execute('CREATE TABLE sales (sale_date TEXT, total_amount NUMERIC)')
        connection.executemany('INSERT INTO sales VALUES (?, ?)', [
            ('2025-10-01', 100),
            ('2026-10-01', 250),
            ('2026-10-31', 75),
            ('2026-11-01', 50),
        ])
        return connection

    def test_four_filters_and_no_matches_through_all_layers(self):
        cases = [('', 475.0), ('?year=2026', 375.0), ('?month=10', 425.0),
                 ('?year=2026&month=10', 325.0), ('?year=2024', 0.0)]
        for query, expected in cases:
            with self.subTest(query=query), patch(
                'app.repositories.sqlserver.sales_repository.get_sqlserver_connection',
                side_effect=self.fixture_connection,
            ):
                response = self.client.get('/analytics/sales-total' + query)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), {
                    'indicator': 'sales_total', 'title': 'Ventas Totales',
                    'chart_type': 'card', 'data': expected, 'sources': ['SQL Server'],
                })

    def test_invalid_filters_do_not_call_service(self):
        cases = [
            ('?month=15', ['El mes debe estar entre 1 y 12']),
            ('?year=abc', ['El año debe ser un número entero']),
            ('?year=abc&month=15', ['El año debe ser un número entero', 'El mes debe estar entre 1 y 12']),
            ('?year=0', ['El año debe estar entre 1 y 9999']),
            ('?year=10000', ['El año debe estar entre 1 y 9999']),
            ('?month=0', ['El mes debe estar entre 1 y 12']),
            ('?month=-1', ['El mes debe estar entre 1 y 12']),
            ('?year=', ['El año debe ser un número entero']),
            ('?month=', ['El mes debe ser un número entero']),
            ('?year=2026.5', ['El año debe ser un número entero']),
            ('?month=1.5', ['El mes debe ser un número entero']),
            ('?year=2026%20OR%201=1', ['El año debe ser un número entero']),
        ]
        with patch('app.routes.sales_routes.service.total_sales') as service:
            for query, expected in cases:
                with self.subTest(query=query):
                    response = self.client.get('/analytics/sales-total' + query)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json(), {
                        'message': 'Error en los parámetros enviados', 'errors': expected,
                    })
            service.assert_not_called()

    def test_valid_boundary_values_reach_service_as_integers(self):
        from app.schemas.analytics_schema import IndicatorResponse
        result = IndicatorResponse('sales_total', 'Ventas Totales', 'card', 0.0, ['SQL Server'])
        for year, month in [(1, 1), (9999, 12)]:
            with self.subTest(year=year, month=month), patch(
                'app.routes.sales_routes.service.total_sales', return_value=result,
            ) as service:
                response = self.client.get(f'/analytics/sales-total?year={year}&month={month}')
                self.assertEqual(response.status_code, 200)
                service.assert_called_once_with(year=year, month=month)

    def test_sql_uses_placeholders_and_closes_connection(self):
        cases = [(None, None, [], ''), (2026, None, [2026], 'YEAR(sale_date) = ?'),
                 (None, 10, [10], 'MONTH(sale_date) = ?'),
                 (2026, 10, [2026, 10], 'YEAR(sale_date) = ? AND MONTH(sale_date) = ?')]
        for year, month, params, condition in cases:
            with self.subTest(year=year, month=month):
                connection = Mock()
                cursor = connection.cursor.return_value
                cursor.fetchone.return_value = (Decimal('123.45'),)
                with patch('app.repositories.sqlserver.sales_repository.get_sqlserver_connection', return_value=connection):
                    self.assertEqual(SalesRepository().get_total_sales(year, month), 123.45)
                query, actual_params = cursor.execute.call_args.args
                normalized = ' '.join(query.split())
                self.assertEqual(actual_params, params)
                self.assertEqual(normalized, 'SELECT COALESCE(SUM(total_amount), 0) FROM sales' +
                                 (' WHERE ' + condition if condition else ''))
                connection.close.assert_called_once()

    def test_connection_closes_on_database_failure(self):
        for method in ['execute', 'fetchone']:
            with self.subTest(method=method):
                connection = Mock()
                getattr(connection.cursor.return_value, method).side_effect = RuntimeError('database failure')
                with patch('app.repositories.sqlserver.sales_repository.get_sqlserver_connection', return_value=connection):
                    with self.assertRaises(RuntimeError):
                        SalesRepository().get_total_sales()
                connection.close.assert_called_once()

    def test_swagger_optional_parameters_and_validation_response(self):
        path = Path(__file__).resolve().parents[1] / 'app/static/swagger.json'
        paths = json.loads(path.read_text(encoding='utf-8'))['paths']
        self.assertNotIn('/analytics/sales-by-month', paths)
        operation = paths['/analytics/sales-total']['get']
        self.assertIn('400', operation['responses'])
        # Campos de texto permiten enviar entradas inválidas para demostrar el HTTP 400 real.
        self.assertEqual([(p['name'], p['required'], p['type'])
                          for p in operation['parameters']],
                         [('year', False, 'string'), ('month', False, 'string')])
