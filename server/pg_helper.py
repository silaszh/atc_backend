import os

import psycopg2
from psycopg2.extras import Json, DictCursor
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
            "UPDATE seat SET last_login_time = NOW() WHERE seat_id =%s", (seat_id,)
        )
        self.connection.commit()
        cursor.close()

    def get_seat_by_id(self, seat_id):
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT seat_id, name, last_login_time FROM seat WHERE seat_id = %s",
            (seat_id,),
        )
        seat = cursor.fetchone()
        cursor.close()
        return seat

    def get_seat_by_name(self, name):
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT seat_id, name, last_login_time FROM seat WHERE name = %s",
            (name,),
        )
        seat = cursor.fetchone()
        cursor.close()
        return seat

    def insert_state(self, seat_id, timestamp, state_data):
        # 保证 seat_id, timestamp 不为空
        cursor = self.connection.cursor()
        if not state_data:
            query = f"INSERT INTO state (seat_id, timestamp) VALUES (%s, %s)"
        else:
            columns = ", ".join(state_data.keys())
            values = ", ".join(["%s"] * len(state_data))
            query = f"INSERT INTO state (seat_id, timestamp, {columns}) VALUES (%s, %s, {values})"

        cursor.execute(query, (seat_id, timestamp) + tuple(state_data.values()))
        self.connection.commit()
        cursor.close()

    def get_all_states(self, number_per_seat=5):
        cursor = self.connection.cursor(cursor_factory=DictCursor)
        query = """\
SELECT * FROM (
  SELECT
    s.*,
    ROW_NUMBER() OVER (PARTITION BY seat_id ORDER BY "timestamp" DESC) AS rn
  FROM state s
) t
WHERE t.rn <= %s
ORDER BY t.seat_id, t."timestamp" DESC;
"""
        cursor.execute(query, (number_per_seat,))
        states = cursor.fetchall()
        cursor.close()
        states = [dict(row) for row in states]
        for state in states:
            state.pop("rn", None)
            state["timestamp"] = state["timestamp"].isoformat()
        return states

    def create_chat(self):
        cursor = self.connection.cursor()
        cursor.execute("INSERT INTO chat (time) VALUES (NOW()) RETURNING chat_id")
        chat_id = cursor.fetchone()[0]
        self.connection.commit()
        cursor.close()
        return chat_id

    def update_chat(self, chat_id, title=None):
        """
        更新chat，修改title和更新时间
        """
        cursor = self.connection.cursor()
        if title is None:
            cursor.execute(
                "UPDATE chat SET time = NOW() WHERE chat_id = %s", (chat_id,)
            )
        else:
            cursor.execute(
                "UPDATE chat SET title = %s, time = NOW() WHERE chat_id = %s",
                (title, chat_id),
            )
        self.connection.commit()
        cursor.close()

    def get_chats(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT chat_id, title, time FROM chat ORDER BY time DESC")
        chats = [
            {"chat_id": row[0], "title": row[1], "time": row[2]}
            for row in cursor.fetchall()
        ]
        cursor.close()
        return chats

    def append_msg_to_chat(self, chat_id, msg):
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO message (chat_id, time, content) VALUES (%s, NOW(), %s)",
            (chat_id, Json(msg)),
        )
        self.connection.commit()
        cursor.close()

    def get_msg_of_chat(self, chat_id):
        cursor = self.connection.cursor()
        cursor.execute(
            "SELECT content FROM message WHERE chat_id = %s ORDER BY time ASC",
            (chat_id,),
        )
        messages = [row[0] for row in cursor.fetchall()]
        cursor.close()
        return messages

    def insert_alert(self, seat_id, timestamp, summary, level):
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO alert (seat_id, timestamp, summary, level) VALUES (%s, %s, %s, %s) RETURNING alert_id",
            (seat_id, timestamp, summary, level),
        )
        alert_id = cursor.fetchone()[0]
        self.connection.commit()
        cursor.close()
        return alert_id

    def update_alert(self, alert_id, reason, suggestion, video, tag):
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE alert SET settled = FALSE, reason = %s, suggestion = %s, video = %s, tag = %s WHERE alert_id = %s",
            (reason, suggestion, video, Json(tag), alert_id),
        )
        self.connection.commit()
        cursor.close()

    def settle_alert(self, alert_id):
        cursor = self.connection.cursor()
        cursor.execute(
            "UPDATE alert SET settled = TRUE WHERE alert_id = %s",
            (alert_id,),
        )
        self.connection.commit()
        cursor.close()

    def get_all_alerts(self, page=1, page_size=20):
        cursor = self.connection.cursor(cursor_factory=DictCursor)
        cursor.execute(
            "SELECT alert_id, seat_id, timestamp, summary, level, settled FROM alert ORDER BY timestamp DESC LIMIT %s OFFSET %s",
            (page_size, (page - 1) * page_size),
        )
        alerts = cursor.fetchall()
        cursor.close()
        return [dict(alert) for alert in alerts]

    def get_alert_by_alert_id(self, alert_id):
        cursor = self.connection.cursor(cursor_factory=DictCursor)
        cursor.execute(
            "SELECT * FROM alert WHERE alert_id = %s ORDER BY timestamp DESC",
            (alert_id,),
        )
        alerts = cursor.fetchone()
        cursor.close()
        return dict(alerts) if alerts else None

    def close(self):
        if self.connection:
            self.connection.close()


def get_helper():
    return PgHelper()
