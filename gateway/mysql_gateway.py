# gateway/mysql_db_gateway.py
import pymysql
import pymysql.cursors
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "deped-db"),  # Changed from MYSQL_DB
        port=int(os.getenv("MYSQL_PORT", 3306)),
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor  # Returns results as dictionaries
    )

def fetch_query(sql, params=None):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params or [])
        return cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def query(sql, params=None):
    """
    Executes an INSERT, UPDATE, DELETE, or other write query.
    Returns a dict with statusCode and message.
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params or [])
        conn.commit()
        return {"statusCode": 200, "message": "Query executed successfully"}
    except pymysql.Error as e:
        return {"statusCode": 500, "message": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def query_insert(sql, params=None):
    """
    Executes an INSERT and returns the lastrowid.
    Returns a dict with statusCode and insertId.
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params or [])
        conn.commit()
        return {"statusCode": 200, "insertId": cursor.lastrowid}
    except pymysql.Error as e:
        return {"statusCode": 500, "message": str(e)}
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def recalculate_ledger_snapshots(employee_id: int, leave_type_id: int) -> float:
    """
    Recomputes balance_snapshot_after for every ledger row for a given employee and
    leave type, ordered chronologically by transaction_date then id — like an Excel
    running total. Updates employee_leave_balances cache with the final computed balance.
    Call this after every INSERT into leave_credit_transactions.

    Parameters:
        employee_id (int): The employee whose ledger rows to recalculate.
        leave_type_id (int): The leave type to recalculate.

    Returns:
        float: The final running balance after all transactions are applied in order.
    """
    rows = fetch_query(  # fetch all transactions for this employee/leave type in chronological order
        """SELECT id, transaction_type, amount
           FROM leave_credit_transactions
           WHERE employee_id = %s AND leave_type_id = %s
           ORDER BY transaction_date ASC, id ASC""",
        [employee_id, leave_type_id]
    )

    running = 0.0  # start running balance from zero (before any transactions)

    for row in rows:  # walk each transaction in chronological order
        amount = float(row["amount"])  # cast Decimal to float for arithmetic
        if row["transaction_type"] == "CREDIT":  # credit increases the balance
            running = round(running + amount, 2)  # add credit amount to running total
        else:  # DEBIT decreases the balance
            running = round(running - amount, 2)  # subtract debit amount from running total

        query(  # update this row's snapshot with the recalculated running balance
            "UPDATE leave_credit_transactions SET balance_snapshot_after = %s WHERE id = %s",
            [running, row["id"]]
        )

    query(  # upsert the balance cache with the final balance from the ledger
        """INSERT INTO employee_leave_balances (employee_id, leave_type_id, balance)
           VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE balance = %s""",
        [employee_id, leave_type_id, running, running]
    )

    return running  # return the final computed balance