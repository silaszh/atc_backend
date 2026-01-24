import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

PGSQL_USER = os.getenv("PGSQL_USER")
PGSQL_PASSWORD = os.getenv("PGSQL_PASSWORD")
PGSQL_HOST = os.getenv("PGSQL_HOST")
PGSQL_PORT = os.getenv("PGSQL_PORT")
PGSQL_DB = os.getenv("PGSQL_DB")


class PgHelper:
    def __init__(self, user=None, password=None, host=None, port=None, database=None):
        self.connection = psycopg2.connect(
            user=user or PGSQL_USER,
            password=password or PGSQL_PASSWORD,
            host=host or PGSQL_HOST,
            port=port or PGSQL_PORT,
            database=database or PGSQL_DB,
        )

    def get_all_seats(self):
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT seat_id, name, last_login_time FROM seat ORDER BY seat_id ASC"
        )
        seats = cursor.fetchall()
        cursor.close()
        return seats

    def update_login_time(self, seat_id):
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE seat SET last_login_time = NOW() WHERE seat_id=%s", (seat_id,)
        )
        self.connection.commit()
        cursor.close()

    def close(self):
        if self.connection:
            self.connection.close()


def get_helper():
    return PgHelper()
