from app.database.sqlserver import get_sqlserver_connection


class SalesRepository:


    # ==========================================
    # INDICADOR SIMPLE
    # Total de ventas
    # ==========================================

    def get_total_sales(self, year=None, month=None):
        query = """
            SELECT COALESCE(SUM(total_amount), 0)
            FROM sales
        """
        conditions = []
        params = []

        if year is not None:
            conditions.append("YEAR(sale_date) = ?")
            params.append(year)

        if month is not None:
            conditions.append("MONTH(sale_date) = ?")
            params.append(month)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        connection = get_sqlserver_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(query, params)
            result = cursor.fetchone()
            return float(result[0] or 0)
        finally:
            connection.close()


    # ==========================================
    # INDICADOR INTEGRADO
    # Producto más vendido
    # ==========================================

    def get_top_product(self):

        connection = get_sqlserver_connection()

        cursor = connection.cursor()


        query = """

        SELECT TOP 1

            product_id,

            SUM(quantity) AS total_quantity


        FROM sales_detail


        GROUP BY product_id


        ORDER BY total_quantity DESC

        """


        cursor.execute(query)


        result = cursor.fetchone()


        connection.close()



        if result:

            return {

                "product_id": result[0],

                "quantity": result[1]

            }


        return None