import os
import sys
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# DB config
# --------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "food-tasters.cctysvuxscld.us-east-1.rds.amazonaws.com"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "recipes"),
    "user": os.getenv("DB_USER", "foodies"),
    "password": os.getenv("DB_PASSWORD", "Capstone699MADS!"),
    "sslmode": os.getenv("DB_SSLMODE", "require"),
}

# --------------------------------------------------
# Connection utilities
# --------------------------------------------------
def get_connection() -> psycopg.Connection:
    return psycopg.connect(**DB_CONFIG, row_factory=dict_row)


@contextmanager
def get_db():
    conn = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


# --------------------------------------------------
# Health check
# --------------------------------------------------
def test_connection():
    try:
        row = None
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT NOW();")
                row = cur.fetchone()

        print("Database connected successfully")
        return True

    except Exception as e:
        print("Connection failed:")
        print(type(e).__name__)
        print(e)
        return False


# --------------------------------------------------
# Main
# --------------------------------------------------
def main():
    if test_connection():
        sys.exit(0)   # success → exit immediately
    else:
        sys.exit(1)   # failure → exit with error code


if __name__ == "__main__":
    main()