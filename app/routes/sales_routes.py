from flask import Blueprint, jsonify, request

from app.services.analytics.sales_service import SalesService


sales_bp = Blueprint("sales", __name__)
service = SalesService()


def get_date_filters():
    """Valida los filtros opcionales antes de consultar la base de datos."""
    year_raw = request.args.get("year")
    month_raw = request.args.get("month")
    errors = []
    year = None
    month = None

    if year_raw is not None:
        try:
            year = int(year_raw)
            if not 1 <= year <= 9999:
                errors.append("El año debe estar entre 1 y 9999")
        except ValueError:
            errors.append("El año debe ser un número entero")

    if month_raw is not None:
        try:
            month = int(month_raw)
            if not 1 <= month <= 12:
                errors.append("El mes debe estar entre 1 y 12")
        except ValueError:
            errors.append("El mes debe ser un número entero")

    if errors:
        return None, None, (jsonify({
            "message": "Error en los parámetros enviados",
            "errors": errors,
        }), 400)

    return year, month, None


@sales_bp.route("/analytics/sales-total", methods=["GET"])
def sales_total():
    year, month, error = get_date_filters()
    if error is not None:
        return error

    result = service.total_sales(year=year, month=month)
    return jsonify(result.__dict__)
