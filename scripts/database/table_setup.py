
import os
import psycopg
from dotenv import load_dotenv

# --------------------------------------------------
# Load environment variables from .env
# --------------------------------------------------
load_dotenv("connect.env")

# --------------------------------------------------
# Connection configuration
# --------------------------------------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "sslmode": os.getenv("DB_SSLMODE", "require"),
}

# --------------------------------------------------
# Create enum types
# --------------------------------------------------
CREATE_TYPES_SQL = """
DO $$ BEGIN
    CREATE TYPE difficulty_enum AS ENUM ('beginner', 'intermediate', 'advanced');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE nutrition_content_enum AS ENUM ('high', 'medium', 'low', 'unknown');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE cuisine_enum AS ENUM (
        'asian',
        'european',
        'mediterranean',
        'american',
        'african',
        'latin',
        'fusion',
        'unknown'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE cooking_method_enum AS ENUM (
        'steam',
        'sautee',
        'grill',
        'broil',
        'fry',
        'boil',
        'sous_vide',
        'poach',
        'simmer',
        'braise',
        'stew',
        'bake',
        'roast',
        'stir_fry',
        'unknown'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
"""

# --------------------------------------------------
# Main table
# RDS stores only indexed fields plus the S3 key
# recipe_id comes from the CSV RecipeId
# --------------------------------------------------
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS recipes (
    recipe_id BIGSERIAL PRIMARY KEY,
    original_id VARCHAR(100) NOT NULL,
    source VARCHAR(100) NOT NULL,
    cuisine cuisine_enum DEFAULT 'unknown',
    cooking_method cooking_method_enum[] DEFAULT ARRAY['unknown']::cooking_method_enum[],
    difficulty difficulty_enum,
    protein_content nutrition_content_enum DEFAULT 'unknown',
    fiber_content nutrition_content_enum DEFAULT 'unknown',
    fat_content nutrition_content_enum DEFAULT 'unknown',
    carbohydrate_content nutrition_content_enum DEFAULT 'unknown',
    sodium_content nutrition_content_enum DEFAULT 'unknown',
    s3_key TEXT UNIQUE
);
"""

# --------------------------------------------------
# Table cleanup
# --------------------------------------------------

DROP_SQL = """
-- Drop table first (depends on enums)
DROP TABLE IF EXISTS recipes CASCADE;

-- Drop enum types (must be done AFTER dropping tables)
DO $$ BEGIN
    DROP TYPE IF EXISTS cuisine_enum CASCADE;
EXCEPTION
    WHEN undefined_object THEN null;
END $$;

DO $$ BEGIN
    DROP TYPE IF EXISTS cooking_method_enum CASCADE;
EXCEPTION
    WHEN undefined_object THEN null;
END $$;

DO $$ BEGIN
    DROP TYPE IF EXISTS difficulty_enum CASCADE;
EXCEPTION
    WHEN undefined_object THEN null;
END $$;

DO $$ BEGIN
    DROP TYPE IF EXISTS nutrition_content_enum CASCADE;
EXCEPTION
    WHEN undefined_object THEN null;
END $$;
"""

# --------------------------------------------------
# Indexes
# --------------------------------------------------
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_recipes_cuisine ON recipes(cuisine);
CREATE INDEX IF NOT EXISTS idx_recipes_cooking_method_gin ON recipes USING GIN (cooking_method);
CREATE INDEX IF NOT EXISTS idx_recipes_difficulty ON recipes(difficulty);
CREATE INDEX IF NOT EXISTS idx_recipes_protein_content ON recipes(protein_content);
CREATE INDEX IF NOT EXISTS idx_recipes_fiber_content ON recipes(fiber_content);
CREATE INDEX IF NOT EXISTS idx_recipes_fat_content ON recipes(fat_content);
CREATE INDEX IF NOT EXISTS idx_recipes_carbohydrate_content ON recipes(carbohydrate_content);
CREATE INDEX IF NOT EXISTS idx_recipes_sodium_content ON recipes(sodium_content);
CREATE INDEX IF NOT EXISTS idx_recipes_s3_key ON recipes(s3_key);
"""

def run_sql(cursor, sql, label):
    print(f"Running: {label}")
    cursor.execute(sql)
    print(f"Completed: {label}\n")

def create_schema():
    conn = None
    cursor = None

    try:
        conn = psycopg.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()

        run_sql(cursor, DROP_SQL, "drop existing schema")
        run_sql(cursor, CREATE_TYPES_SQL, "create enum types")
        run_sql(cursor, CREATE_TABLES_SQL, "create tables")
        run_sql(cursor, CREATE_INDEXES_SQL, "create indexes")

        print("Schema created successfully.")

    except Exception as e:
        print(f"Error creating schema: {e}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    create_schema()
