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