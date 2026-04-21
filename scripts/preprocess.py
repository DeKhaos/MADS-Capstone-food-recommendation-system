import ast
import configparser
import io
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
import pandas as pd
import psycopg
from botocore.config import Config
from dotenv import load_dotenv

from difficulty_scoring import compute_recipe_difficulty
from nutrition_classifier import build_nutrition_labels


AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")
S3_BUCKET = "food-tasters-recipe-674880355625-us-east-1-an"

# Better default for IO bound Bedrock calls
DEFAULT_MAX_WORKERS = int(os.getenv("PIPELINE_MAX_WORKERS", "8"))

load_dotenv("../.env")

VALID_CUISINES = {
    "asian",
    "european",
    "american",
    "african",
    "fusion",
    "unknown",
    "mediterranean",
    "latin",
}

CUISINE_MAP = {
    "chinese": "asian",
    "japanese": "asian",
    "thai": "asian",
    "korean": "asian",
    "vietnamese": "asian",
    "filipino": "asian",
    "indian": "asian",
    "italian": "european",
    "french": "european",
    "german": "european",
    "spanish": "european",
    "greek": "european",
    "middle eastern": "mediterranean",
    "levantine": "mediterranean",
    "turkish": "mediterranean",
    "mexican": "latin",
    "tex-mex": "fusion",
    "southern": "american",
    "cajun": "american",
    "bbq": "american",
    "moroccan": "african",
    "ethiopian": "african",
}

VALID_COOKING_METHODS = {
    "steam",
    "sautee",
    "grill",
    "broil",
    "fry",
    "boil",
    "sous_vide",
    "poach",
    "simmer",
    "braise",
    "stew",
    "bake",
    "roast",
    "stir_fry",
    "unknown",
}

COOKING_METHOD_MAP = {
    "saute": "sautee",
    "sauté": "sautee",
    "pan fry": "fry",
    "deep fry": "fry",
    "stir fry": "stir_fry",
    "stir-fry": "stir_fry",
    "baking": "bake",
    "oven bake": "bake",
    "roasting": "roast",
    "oven roast": "roast",
    "slow cook": "stew",
    "slow cooker": "stew",
    "sear": "sautee",
}


def build_system_prompt() -> str:
    return """You are a food recipe enrichment engine.

Do not include explanations.
Do not include markdown.
Do not include code fences.
Do not include comments.

The first character of your response must be {
The last character must be }

Classify cleaned recipe records into structured JSON
for a food recommendation system.

Important classification rules:

1. Use only structured recipe content such as title, ingredients, instructions, and nutrition fields for cuisine and allergens.

2. meal_type should be limited to:
breakfast, lunch, dinner, dessert, beverage

3. allergens should be limited to:
celery, gluten, crustaceans, eggs, fish, lupin, milk, molluscs, mustard, nuts, peanuts, sesame seeds, sulphur dioxide, soy

4. cuisine must be limited to:
asian, european, mediterranean, american, african, fusion, latin, unknown

5. Map narrower cuisines into broader cuisine buckets:
chinese, japanese, thai, korean, vietnamese, filipino, indian -> asian
italian, french, german, spanish, british, greek -> european
middle eastern, levantine, turkish -> mediterranean
mexican, south american, peruvian, argentinean, brazilian, andean, colombian, venezuelan, cubin, puerto rican, dominican -> latin
southern, cajun, bbq, tex-mex, classic american -> american
moroccan, ethiopian, west african -> african

6. cooking_methods should be limited to:
steam, sautee, grill, broil, fry, boil, sous_vide, poach, simmer, braise, stew, bake, roast, stir_fry, unknown

7. Map near matches to the closest allowed cooking method:
saute -> sautee
pan fry, deep fry -> fry
stir fry, stir-fry -> stir_fry
bake, oven bake -> bake
roast, oven roast -> roast
slow cook -> stew
sear -> sautee when used as the main method

Return JSON only.

Schema:

{
  "recipe_id": "string",
  "cuisine": ["string"],
  "meal_type": ["string"],
  "allergens": ["string"],
  "cooking_methods": ["string"]
}"""


SYSTEM_PROMPT = build_system_prompt()
SYSTEM_MESSAGE = [{"text": SYSTEM_PROMPT}]


def parse_aws_credential_block(text: str) -> Tuple[str, str, Optional[str]]:
    parser = configparser.ConfigParser()
    parser.read_file(io.StringIO(text.strip()))

    if "default" not in parser:
        raise ValueError("Credential block must contain a [default] profile.")

    profile = parser["default"]
    access_key = profile.get("aws_access_key_id")
    secret_key = profile.get("aws_secret_access_key")
    session_token = profile.get("aws_session_token")

    if not access_key or not secret_key:
        raise ValueError("Missing aws_access_key_id or aws_secret_access_key.")

    return access_key, secret_key, session_token


def prompt_for_aws_credential_block() -> str:
    print("\nPaste the AWS credential block exactly as provided.")
    print("Press ENTER twice when finished.\n")

    lines: List[str] = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    credential_text = "\n".join(lines).strip()
    if not credential_text:
        raise ValueError("No AWS credential block was provided.")

    return credential_text


def build_aws_session(credential_block: str) -> boto3.session.Session:
    access_key, secret_key, session_token = parse_aws_credential_block(credential_block)
    return boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name=AWS_REGION,
    )


def build_bedrock_client(session: boto3.session.Session):
    return session.client(
        "bedrock-runtime",
        config=Config(
            read_timeout=3600,
            retries={"max_attempts": 8, "mode": "standard"},
            max_pool_connections=50,
        ),
    )


def build_s3_client(session: boto3.session.Session):
    return session.client(
        "s3",
        config=Config(
            retries={"max_attempts": 8, "mode": "standard"},
            max_pool_connections=50,
        ),
    )


def build_rds_connection() -> psycopg.Connection:
    db_config = {
        "host": os.getenv("DB_HOST"),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "sslmode": os.getenv("DB_SSLMODE", "require"),
    }

    missing = [k for k, v in db_config.items() if v is None and k != "port"]
    if missing:
        raise ValueError(
            "Missing database settings in .env or environment variables: "
            + ", ".join(missing)
        )

    return psycopg.connect(**db_config)


def build_user_prompt(recipe: Dict[str, Any]) -> str:
    return f"""Classify this recipe.

Recipe:

{json.dumps(recipe, ensure_ascii=False, indent=2)}"""


def extract_json_from_text(text: str) -> Dict[str, Any]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response: {text[:500]}")
    return json.loads(match.group())


def call_bedrock_for_recipe(bedrock_client, recipe_for_prompt: Dict[str, Any]) -> Dict[str, Any]:
    response = bedrock_client.converse(
        modelId=BEDROCK_MODEL_ID,
        system=SYSTEM_MESSAGE,
        messages=[
            {
                "role": "user",
                "content": [{"text": build_user_prompt(recipe_for_prompt)}],
            }
        ],
        inferenceConfig={
            "temperature": 0,
            "maxTokens": 600,
        },
    )

    output_text = response["output"]["message"]["content"][0]["text"]
    return extract_json_from_text(output_text)


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> Optional[int]:
    x = safe_float(value)
    return None if x is None else int(round(x))


def normalize_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_list_like(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except (ValueError, SyntaxError):
        pass

    if "\n" in text:
        return [part.strip() for part in text.split("\n") if part.strip()]

    if "|" in text:
        return [part.strip() for part in text.split("|") if part.strip()]

    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]

    return [text]


def normalize_text_list(values: Iterable[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()

    for value in values:
        item = str(value).strip().lower()
        if not item:
            continue
        if item not in seen:
            seen.add(item)
            cleaned.append(item)

    return cleaned


def normalize_cuisine_for_rds(cuisine_values: List[str]) -> str:
    for value in cuisine_values:
        item = value.strip().lower()
        item = CUISINE_MAP.get(item, item)

        if item in VALID_CUISINES:
            return item

    return "unknown"


def normalize_cooking_method_for_rds(cooking_method_values: List[str]) -> List[str]:
    normalized = []
    seen = set()

    for value in cooking_method_values:
        item = value.strip().lower()
        item = COOKING_METHOD_MAP.get(item, item)

        if item in VALID_COOKING_METHODS and item not in seen:
            seen.add(item)
            normalized.append(item)

    return normalized or ["unknown"]


def extract_difficulty_label(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return value.get("difficulty_label")
    if isinstance(value, str):
        text = value.strip().lower()
        return text or None
    return None


def normalize_meal_type(values: List[str]) -> List[str]:
    allowed = {
        "breakfast": "breakfast",
        "lunch": "lunch",
        "dinner": "dinner",
        "dessert": "dessert",
        "beverage": "beverage",
        "beverages": "beverage",
    }
    normalized = []
    seen = set()
    for value in values:
        key = value.strip().lower()
        if key in allowed:
            mapped = allowed[key]
            if mapped not in seen:
                seen.add(mapped)
                normalized.append(mapped)
    return normalized


def pick_prompt_ingredients(row: Dict[str, Any]) -> List[str]:
    for key in [
        "ingredients_canonical_final_le_5_replace",
        "ingredients_canonical_final",
        "ingredients_canonical_auto",
        "ingredients_canonical",
        "RecipeIngredientParts",
        "RecipeIngredientParts_old",
    ]:
        items = parse_list_like(row.get(key))
        if items:
            return items
    return []


def build_recipe_for_prompt(row: Dict[str, Any]) -> Dict[str, Any]:
    ingredients = pick_prompt_ingredients(row)
    instructions = parse_list_like(row.get("RecipeInstructions"))

    return {
        "recipe_id": str(row.get("RecipeId") or "").strip(),
        "title": normalize_string(row.get("Name")),
        "ingredients": ingredients,
        "instructions": instructions,
        "calories": safe_float(row.get("Calories")),
        "fat_content": safe_float(row.get("FatContent")),
        "carbohydrate_content": safe_float(row.get("CarbohydrateContent")),
        "fiber_content": safe_float(row.get("FiberContent")),
        "protein_content": safe_float(row.get("ProteinContent")),
        "sodium_content": safe_float(row.get("SodiumContent")),
    }


def build_s3_recipe_payload(
    row: Dict[str, Any],
    llm_result: Dict[str, Any],
    nutrition_labels: Dict[str, str],
    difficulty_result: Dict[str, Any],
    prompt_ingredients: List[str],
    instructions: List[str],
) -> Dict[str, Any]:
    cuisine_list = normalize_text_list(llm_result.get("cuisine", []))
    meal_type_list = normalize_meal_type(normalize_text_list(llm_result.get("meal_type", [])))
    allergen_list = normalize_text_list(llm_result.get("allergens", []))
    cooking_method_list = normalize_text_list(llm_result.get("cooking_methods", []))

    return {
        "recipe_id": None,
        "original_id": str(row.get("RecipeId")).strip(),
        "source": normalize_string(row.get("source")) or normalize_string(row.get("Source")) or "unknown",
        "cuisine": normalize_cuisine_for_rds(cuisine_list),
        "meal_type": meal_type_list,
        "allergens": allergen_list,
        "cooking_methods": cooking_method_list,
        "protein_content": nutrition_labels["protein_content"],
        "fiber_content": nutrition_labels["fiber_content"],
        "fat_content": nutrition_labels["fat_content"],
        "carbohydrate_content": nutrition_labels["carbohydrate_content"],
        "sodium_content": nutrition_labels["sodium_content"],
        "difficulty": difficulty_result,
        "calories": safe_int(row.get("Calories")),
        "ingredients": {
            "raw": parse_list_like(row.get("RecipeIngredientParts")),
            "canonical": prompt_ingredients,
        },
        "instructions": instructions,
        "who_score": safe_float(row.get("WHO_Score")),
        "fsa_score": safe_float(row.get("FSA_Score")),
        "prep_time": safe_int(row.get("PrepTime_Minutes")),
        "cook_time": safe_int(row.get("CookTime_Minutes")),
        "total_time": safe_int(row.get("TotalTime_Minutes")),
        "image_url": normalize_string(row.get("Images")),
    }


def upload_json_to_s3(s3_client, bucket: str, key: str, payload: Dict[str, Any]) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def insert_recipe_batch_to_rds(
    conn: psycopg.Connection,
    recipe_payloads: List[Dict[str, Any]]
) -> Dict[str, int]:
    id_map: Dict[str, int] = {}

    with conn.cursor() as cur:
        for payload in recipe_payloads:
            original_id = str(payload["original_id"]).strip()
            source = normalize_string(payload.get("source")) or "unknown"
            difficulty_enum = extract_difficulty_label(payload.get("difficulty"))

            cur.execute(
                """
                INSERT INTO recipes (
                    original_id,
                    source,
                    cuisine,
                    cooking_method,
                    difficulty,
                    protein_content,
                    fiber_content,
                    fat_content,
                    carbohydrate_content,
                    sodium_content,
                    s3_key
                )
                VALUES (
                    %s,
                    %s,
                    %s::cuisine_enum,
                    %s::cooking_method_enum[],
                    %s::difficulty_enum,
                    %s::nutrition_content_enum,
                    %s::nutrition_content_enum,
                    %s::nutrition_content_enum,
                    %s::nutrition_content_enum,
                    %s::nutrition_content_enum,
                    NULL
                )
                RETURNING recipe_id
                """,
                (
                    original_id,
                    source,
                    payload.get("cuisine", "unknown"),
                    normalize_cooking_method_for_rds(payload.get("cooking_methods", [])),
                    difficulty_enum,
                    payload.get("protein_content", "unknown"),
                    payload.get("fiber_content", "unknown"),
                    payload.get("fat_content", "unknown"),
                    payload.get("carbohydrate_content", "unknown"),
                    payload.get("sodium_content", "unknown"),
                ),
            )

            id_map[original_id] = cur.fetchone()[0]

    return id_map


def update_recipe_s3_keys_batch(
    conn: psycopg.Connection,
    updates: List[Tuple[str, int]],
) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            UPDATE recipes
            SET s3_key = %s
            WHERE recipe_id = %s
            """,
            updates,
        )


def classify_row(row: Dict[str, Any], bedrock_client) -> Dict[str, Any]:
    prompt_recipe = build_recipe_for_prompt(row)
    recipe_id = prompt_recipe["recipe_id"]
    if not recipe_id:
        raise ValueError("Recipe row is missing RecipeId.")

    prompt_ingredients = prompt_recipe["ingredients"]
    instructions = prompt_recipe["instructions"]

    llm_result = call_bedrock_for_recipe(bedrock_client, prompt_recipe)

    nutrition_labels = build_nutrition_labels(
        row,
        servings_key="RecipeServings_fill",
        protein_key="ProteinContent",
        fiber_key="FiberContent",
        fat_key="FatContent",
        carbohydrate_key="CarbohydrateContent",
        sodium_key="SodiumContent",
        use_per_serving=True,
    )

    difficulty_result = compute_recipe_difficulty(
        total_time_minutes=safe_float(row.get("TotalTime_Minutes")),
        cooking_methods=llm_result.get("cooking_methods", []),
        ingredients=prompt_ingredients,
    )

    return build_s3_recipe_payload(
        row=row,
        llm_result=llm_result,
        nutrition_labels=nutrition_labels,
        difficulty_result=difficulty_result,
        prompt_ingredients=prompt_ingredients,
        instructions=instructions,
    )


def process_batch(
    rows: List[Dict[str, Any]],
    bedrock_client,
    s3_client,
    conn: psycopg.Connection,
    bucket: str,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> List[Dict[str, Any]]:
    recipe_payloads: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(classify_row, row, bedrock_client): row
            for row in rows
        }

        for future in as_completed(future_map):
            row = future_map[future]
            recipe_id = str(row.get("RecipeId")).strip()
            try:
                payload = future.result()
                recipe_payloads.append(payload)
                results.append(
                    {
                        "recipe_id": recipe_id,
                        "status": "classified",
                        "error": "",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "recipe_id": recipe_id,
                        "status": "error",
                        "error": str(exc),
                    }
                )

    success_payloads = [p for p in recipe_payloads if p.get("original_id")]
    if not success_payloads:
        return results

    # One transaction for insert + s3_key updates
    rds_id_map = insert_recipe_batch_to_rds(conn, success_payloads)

    s3_updates: List[Tuple[str, int]] = []
    upload_jobs: List[Tuple[str, Dict[str, Any]]] = []

    for payload in success_payloads:
        original_id = str(payload["original_id"]).strip()
        recipe_id = int(rds_id_map[original_id])
        payload["recipe_id"] = recipe_id

        s3_key = f"recipes/{recipe_id}.json"
        payload["s3_key"] = s3_key
        upload_jobs.append((s3_key, payload))
        s3_updates.append((s3_key, recipe_id))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(upload_json_to_s3, s3_client, bucket, s3_key, payload)
            for s3_key, payload in upload_jobs
        ]
        for future in as_completed(futures):
            future.result()

    update_recipe_s3_keys_batch(conn, s3_updates)
    conn.commit()

    result_by_recipe = {str(r["recipe_id"]): r for r in results}
    final_results: List[Dict[str, Any]] = []

    for payload in success_payloads:
        recipe_id = int(payload["recipe_id"])
        final_results.append(
            {
                "recipe_id": recipe_id,
                "status": "success",
                "s3_key": payload["s3_key"],
                "cuisine": payload.get("cuisine"),
                "difficulty": extract_difficulty_label(payload.get("difficulty")),
                "error": "",
            }
        )
        result_by_recipe.pop(str(payload["original_id"]).strip(), None)

    for leftover in result_by_recipe.values():
        final_results.append(leftover)

    return final_results


def csv_files_in_folder(folder: Path) -> List[Path]:
    return sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".csv"])


def chunk_rows(rows: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
    return [rows[i:i + batch_size] for i in range(0, len(rows), batch_size)]


def process_folder(
    input_folder: str,
    credential_block: str,
    bucket: str = S3_BUCKET,
    limit_per_file: Optional[int] = None,
    save_run_log: bool = True,
    batch_size: int = 25,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> None:
    session = build_aws_session(credential_block)
    bedrock_client = build_bedrock_client(session)
    s3_client = build_s3_client(session)

    folder = Path(input_folder).resolve()
    if not folder.exists():
        raise FileNotFoundError(f"Input folder does not exist: {folder}")

    csv_paths = csv_files_in_folder(folder)
    if not csv_paths:
        raise FileNotFoundError(f"No CSV files found in: {folder}")

    run_rows: List[Dict[str, Any]] = []

    with build_rds_connection() as conn:
        for csv_path in csv_paths:
            print(f"Processing file: {csv_path.name}")
            df = pd.read_csv(csv_path)

            if limit_per_file is not None:
                df = df.head(limit_per_file)

            records = df.to_dict(orient="records")
            batches = chunk_rows(records, batch_size)

            for batch_number, batch in enumerate(batches, start=1):
                print(f"  Batch {batch_number}/{len(batches)}, size={len(batch)}")

                try:
                    batch_results = process_batch(
                        rows=batch,
                        bedrock_client=bedrock_client,
                        s3_client=s3_client,
                        conn=conn,
                        bucket=bucket,
                        max_workers=max_workers,
                    )
                except Exception as exc:
                    conn.rollback()
                    batch_results = [
                        {
                            "recipe_id": str(row.get("RecipeId")).strip(),
                            "status": "error",
                            "error": f"Batch failed: {exc}",
                        }
                        for row in batch
                    ]

                for result in batch_results:
                    run_rows.append(
                        {
                            "file_name": csv_path.name,
                            "recipe_id": result.get("recipe_id"),
                            "status": result.get("status"),
                            "s3_key": result.get("s3_key", ""),
                            "cuisine": result.get("cuisine", ""),
                            "difficulty": result.get("difficulty", ""),
                            "error": result.get("error", ""),
                        }
                    )

            print()

    if save_run_log:
        log_path = folder / "pipeline_run_log.csv"
        pd.DataFrame(run_rows).to_csv(log_path, index=False)
        print(f"Run log saved to: {log_path}")


def process_single_chunk_file(
    csv_file: str,
    credential_block: str,
    bucket: str = S3_BUCKET,
    limit_rows: Optional[int] = None,
    batch_size: int = 25,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> None:
    session = build_aws_session(credential_block)
    bedrock_client = build_bedrock_client(session)
    s3_client = build_s3_client(session)

    csv_path = Path(csv_file).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file does not exist: {csv_path}")

    df = pd.read_csv(csv_path)
    if limit_rows is not None:
        df = df.head(limit_rows)

    records = df.to_dict(orient="records")
    batches = chunk_rows(records, batch_size)
    run_rows: List[Dict[str, Any]] = []

    with build_rds_connection() as conn:
        for batch_number, batch in enumerate(batches, start=1):
            print(f"Processing {csv_path.name}, batch {batch_number}/{len(batches)}, size={len(batch)}")

            try:
                batch_results = process_batch(
                    rows=batch,
                    bedrock_client=bedrock_client,
                    s3_client=s3_client,
                    conn=conn,
                    bucket=bucket,
                    max_workers=max_workers,
                )
            except Exception as exc:
                conn.rollback()
                batch_results = [
                    {
                        "recipe_id": str(row.get("RecipeId")).strip(),
                        "status": "error",
                        "error": f"Batch failed: {exc}",
                    }
                    for row in batch
                ]

            for result in batch_results:
                run_rows.append(
                    {
                        "file_name": csv_path.name,
                        "recipe_id": result.get("recipe_id"),
                        "status": result.get("status"),
                        "s3_key": result.get("s3_key", ""),
                        "cuisine": result.get("cuisine", ""),
                        "difficulty": result.get("difficulty", ""),
                        "error": result.get("error", ""),
                    }
                )

    log_path = csv_path.parent / f"{csv_path.stem}_run_log.csv"
    pd.DataFrame(run_rows).to_csv(log_path, index=False)
    print(f"Run log saved to: {log_path}")


if __name__ == "__main__":
    credential_block = prompt_for_aws_credential_block()

    process_single_chunk_file(
        csv_file="../data/processed/data_chunk_9.csv",
        credential_block=credential_block,
        bucket=S3_BUCKET,
        limit_rows=None,
        batch_size=50,
        max_workers=8,
    )