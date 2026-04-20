import configparser
import io
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import boto3
import psycopg
from dotenv import load_dotenv


AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = "food-tasters-recipe-674880355625-us-east-1-an"

VALID_FILTER_COLUMNS = {
    "recipe_id",
    "original_id",
    "cuisine",
    "cooking_method",
    "difficulty",
    "protein_content",
    "fiber_content",
    "fat_content",
    "carbohydrate_content",
    "sodium_content",
    "s3_key",
}


load_dotenv("database/connect.env")


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


def build_aws_session_from_credential_block(credential_block: str) -> boto3.session.Session:
    access_key, secret_key, session_token = parse_aws_credential_block(credential_block)
    return boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name=AWS_REGION,
    )


def build_s3_client_from_credential_block(credential_block: str):
    session = build_aws_session_from_credential_block(credential_block)
    return session.client("s3")


def build_s3_client(
    aws_access_key_id: str,
    aws_secret_access_key: str,
    aws_session_token: Optional[str] = None,
    region_name: str = AWS_REGION,
):
    session = boto3.session.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
        region_name=region_name,
    )
    return session.client("s3")


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
            "Missing database settings in connect.env or environment variables: "
            + ", ".join(missing)
        )

    return psycopg.connect(**db_config)


def fetch_s3_json(
    s3_client,
    key: str,
    bucket: str = S3_BUCKET,
) -> Dict[str, Any]:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    body = response["Body"].read().decode("utf-8")
    return json.loads(body)


def fetch_s3_text(
    s3_client,
    key: str,
    bucket: str = S3_BUCKET,
    encoding: str = "utf-8",
) -> str:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode(encoding)


def fetch_s3_bytes(
    s3_client,
    key: str,
    bucket: str = S3_BUCKET,
) -> bytes:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def object_exists(
    s3_client,
    key: str,
    bucket: str = S3_BUCKET,
) -> bool:
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def build_where_clause(filters: Optional[Dict[str, Any]]) -> Tuple[str, List[Any]]:
    if not filters:
        return "", []

    clauses: List[str] = []
    params: List[Any] = []

    for column, value in filters.items():
        if column not in VALID_FILTER_COLUMNS:
            raise ValueError(
                f"Invalid filter column: {column}. "
                f"Allowed columns are: {sorted(VALID_FILTER_COLUMNS)}"
            )

        if value is None:
            clauses.append(f"{column} IS NULL")
            continue

        if isinstance(value, (list, tuple, set)):
            values = list(value)
            if not values:
                clauses.append("FALSE")
            else:
                placeholders = ", ".join(["%s"] * len(values))
                clauses.append(f"{column} IN ({placeholders})")
                params.extend(values)
        else:
            clauses.append(f"{column} = %s")
            params.append(value)

    where_sql = " WHERE " + " AND ".join(clauses)
    return where_sql, params


def query_recipes(
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    selected_columns = list(columns) if columns else [
        "recipe_id",
        "original_id",
        "cuisine",
        "cooking_method",
        "difficulty",
        "protein_content",
        "fiber_content",
        "fat_content",
        "carbohydrate_content",
        "sodium_content",
        "s3_key",
    ]

    invalid_columns = [col for col in selected_columns if col not in VALID_FILTER_COLUMNS]
    if invalid_columns:
        raise ValueError(
            f"Invalid selected columns: {invalid_columns}. "
            f"Allowed columns are: {sorted(VALID_FILTER_COLUMNS)}"
        )

    sql = f"""
        SELECT
            {", ".join(selected_columns)}
        FROM recipes
    """

    where_sql, params = build_where_clause(filters)
    sql += where_sql
    sql += " ORDER BY recipe_id"

    with build_rds_connection() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def get_recipe_rows(
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    return query_recipes(filters=filters, columns=columns)


def get_s3_recipe_data_for_rows(
    s3_client,
    rows: Sequence[Dict[str, Any]],
    bucket: str = S3_BUCKET,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []

    for row in rows:
        s3_key = row.get("s3_key")
        if not s3_key:
            results.append(
                {
                    "rds_row": row,
                    "s3_key": None,
                    "s3_data": None,
                    "error": "Missing s3_key in RDS",
                }
            )
            continue

        try:
            s3_data = fetch_s3_json(s3_client=s3_client, key=s3_key, bucket=bucket)
            results.append(
                {
                    "rds_row": row,
                    "s3_key": s3_key,
                    "s3_data": s3_data,
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "rds_row": row,
                    "s3_key": s3_key,
                    "s3_data": None,
                    "error": str(exc),
                }
            )

    return results


def get_all_s3_recipe_data(
    s3_client,
    bucket: str = S3_BUCKET,
) -> List[Dict[str, Any]]:
    rows = query_recipes()
    return get_s3_recipe_data_for_rows(
        s3_client=s3_client,
        rows=rows,
        bucket=bucket,
    )


def get_filtered_s3_recipe_data(
    s3_client,
    filters: Optional[Dict[str, Any]] = None,
    bucket: str = S3_BUCKET,
) -> List[Dict[str, Any]]:
    rows = query_recipes(filters=filters)
    return get_s3_recipe_data_for_rows(
        s3_client=s3_client,
        rows=rows,
        bucket=bucket,
    )


def get_recipe_data_by_ids(
    s3_client,
    recipe_ids: Sequence[Any],
    bucket: str = S3_BUCKET,
) -> List[Dict[str, Any]]:
    rows = query_recipes(filters={"recipe_id": list(recipe_ids)})
    return get_s3_recipe_data_for_rows(
        s3_client=s3_client,
        rows=rows,
        bucket=bucket,
    )


def get_recipe_data_by_original_ids(
    s3_client,
    original_ids: Sequence[Any],
    bucket: str = S3_BUCKET,
) -> List[Dict[str, Any]]:
    rows = query_recipes(filters={"original_id": list(original_ids)})
    return get_s3_recipe_data_for_rows(
        s3_client=s3_client,
        rows=rows,
        bucket=bucket,
    )


def save_results_to_json(results: Sequence[Dict[str, Any]], output_file: str) -> None:
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(list(results), f, indent=2, ensure_ascii=False, default=str)