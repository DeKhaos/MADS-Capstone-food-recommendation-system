import os
import psycopg
from dotenv import load_dotenv

# Load env variables
load_dotenv("connect.env")

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "sslmode": os.getenv("DB_SSLMODE", "require"),
}

def test_query():
    try:
        print("Connecting to RDS...\n")

        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                
                # Test query
                cur.execute("""
                    SELECT *
                    FROM recipes
                    LIMIT 10;
                """)

                rows = cur.fetchall()
                

                print(f"Successfully retrieved {len(rows)} rows\n")

                for i, row in enumerate(rows, start=1):
                    print(f"Row {i}: {row}")

    except Exception as e:
        print("Error connecting to RDS:")
        print(e)


if __name__ == "__main__":
    test_query()