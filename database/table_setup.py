import psycopg
import os

import psycopg
from dotenv import load_dotenv

# --------------------------------------------------
# Load environment variables from .env
# --------------------------------------------------
load_dotenv()

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
    CREATE TYPE difficulty_enum AS ENUM ('easy', 'medium', 'hard', 'expert');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE nutrition_content_enum AS ENUM ('high', 'medium', 'low', 'unknown');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;
"""

# --------------------------------------------------
# Create lookup tables and main tables
# --------------------------------------------------
CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS cuisines (
    cuisine_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS meal_types (
    meal_type_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dietary_tags (
    dietary_tag_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS allergens (
    allergen_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS cooking_methods (
    cooking_method_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS recipes (
    recipe_id VARCHAR(100) PRIMARY KEY,
    cuisine_id BIGINT REFERENCES cuisines(cuisine_id),
    meal_type_id BIGINT REFERENCES meal_types(meal_type_id),
    protein_content nutrition_content_enum,
    fiber_content nutrition_content_enum,
    fat_content nutrition_content_enum,
    carbohydrate_content nutrition_content_enum,
    sodium_content nutrition_content_enum,
    difficulty difficulty_enum,
    calories INTEGER,
    ingredients JSONB,
    instructions JSONB,
    prep_time INTEGER,
    cook_time INTEGER,
    total_time INTEGER,
    review_quantity VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS recipe_dietary_tags (
    id BIGSERIAL PRIMARY KEY,
    recipe_id VARCHAR(100) NOT NULL REFERENCES recipes(recipe_id) ON DELETE CASCADE,
    dietary_tag_id BIGINT NOT NULL REFERENCES dietary_tags(dietary_tag_id) ON DELETE CASCADE,
    UNIQUE (recipe_id, dietary_tag_id)
);

CREATE TABLE IF NOT EXISTS recipe_cooking_methods (
    id BIGSERIAL PRIMARY KEY,
    recipe_id VARCHAR(100) NOT NULL REFERENCES recipes(recipe_id) ON DELETE CASCADE,
    cooking_method_id BIGINT NOT NULL REFERENCES cooking_methods(cooking_method_id) ON DELETE CASCADE,
    UNIQUE (recipe_id, cooking_method_id)
);

CREATE TABLE IF NOT EXISTS recipe_allergens (
    id BIGSERIAL PRIMARY KEY,
    recipe_id VARCHAR(100) NOT NULL REFERENCES recipes(recipe_id) ON DELETE CASCADE,
    allergen_id BIGINT NOT NULL REFERENCES allergens(allergen_id) ON DELETE CASCADE,
    UNIQUE (recipe_id, allergen_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100),
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_allergens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    allergen_id BIGINT NOT NULL REFERENCES allergens(allergen_id) ON DELETE CASCADE,
    UNIQUE (user_id, allergen_id)
);
"""

# --------------------------------------------------
# Seed lookup tables
# ON CONFLICT prevents duplicate inserts
# --------------------------------------------------
SEED_LOOKUPS_SQL = """
INSERT INTO cuisines (name) VALUES
    ('asian'),
    ('european'),
    ('american'),
    ('african'),
    ('mediterranean'),
    ('fusion')
ON CONFLICT (name) DO NOTHING;

INSERT INTO meal_types (name) VALUES
    ('breakfast'),
    ('lunch'),
    ('dinner'),
    ('snack'),
    ('dessert'),
    ('beverage')
ON CONFLICT (name) DO NOTHING;

INSERT INTO dietary_tags (name) VALUES
    ('vegan'),
    ('gluten_free'),
    ('vegetarian'),
    ('keto'),
    ('grain_free'),
    ('seafood')
ON CONFLICT (name) DO NOTHING;

INSERT INTO allergens (name) VALUES
    ('celery'),
    ('gluten'),
    ('crustaceans'),
    ('eggs'),
    ('fish'),
    ('lupin'),
    ('milk'),
    ('molluscs'),
    ('mustard'),
    ('nuts'),
    ('peanuts'),
    ('sesame seeds'),
    ('sulphur dioxide'),
    ('soy')
ON CONFLICT (name) DO NOTHING;

INSERT INTO cooking_methods (name) VALUES
    ('steam'),
    ('sautee'),
    ('grill'),
    ('broil'),
    ('fry'),
    ('boil'),
    ('sous_vide'),
    ('poach'),
    ('simmer'),
    ('braise'),
    ('stew')
ON CONFLICT (name) DO NOTHING;
"""

# --------------------------------------------------
# Optional indexes
# --------------------------------------------------
CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_recipes_cuisine_id ON recipes(cuisine_id);
CREATE INDEX IF NOT EXISTS idx_recipes_meal_type_id ON recipes(meal_type_id);
CREATE INDEX IF NOT EXISTS idx_recipe_dietary_tags_recipe_id ON recipe_dietary_tags(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_cooking_methods_recipe_id ON recipe_cooking_methods(recipe_id);
CREATE INDEX IF NOT EXISTS idx_recipe_allergens_recipe_id ON recipe_allergens(recipe_id);
CREATE INDEX IF NOT EXISTS idx_user_allergens_user_id ON user_allergens(user_id);
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

        run_sql(cursor, CREATE_TYPES_SQL, "create enum types")
        run_sql(cursor, CREATE_TABLES_SQL, "create tables")
        run_sql(cursor, SEED_LOOKUPS_SQL, "seed lookup tables")
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