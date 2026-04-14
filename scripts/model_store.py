import configparser
import io
import json
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import boto3


AWS_REGION = "us-east-1"
S3_BUCKET = "food-tasters-recipe-674880355625-us-east-1-an"
MODEL_PREFIX = "models/"


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


def normalize_model_key(name: str) -> str:
    cleaned = name.strip().lstrip("/")
    if not cleaned:
        raise ValueError("S3 key cannot be empty.")

    if cleaned.startswith(MODEL_PREFIX):
        return cleaned

    return f"{MODEL_PREFIX}{cleaned}"


def upload_model_file(
    s3_client,
    local_path: str,
    s3_key: str,
    bucket: str = S3_BUCKET,
) -> str:
    path = Path(local_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Local file does not exist: {path}")

    final_key = normalize_model_key(s3_key)

    s3_client.upload_file(
        Filename=str(path),
        Bucket=bucket,
        Key=final_key,
    )

    return final_key


def upload_bytes(
    s3_client,
    data: bytes,
    s3_key: str,
    bucket: str = S3_BUCKET,
    content_type: str = "application/octet-stream",
) -> str:
    final_key = normalize_model_key(s3_key)

    s3_client.put_object(
        Bucket=bucket,
        Key=final_key,
        Body=data,
        ContentType=content_type,
    )

    return final_key


def upload_pickle_model(
    s3_client,
    model: Any,
    model_name: str,
    bucket: str = S3_BUCKET,
) -> str:
    cleaned_name = model_name.strip()
    if not cleaned_name:
        raise ValueError("model_name cannot be empty.")

    if not cleaned_name.endswith(".pkl"):
        cleaned_name = f"{cleaned_name}.pkl"

    payload = pickle.dumps(model)
    return upload_bytes(
        s3_client=s3_client,
        data=payload,
        s3_key=cleaned_name,
        bucket=bucket,
        content_type="application/octet-stream",
    )


def upload_json_metadata(
    s3_client,
    metadata: Dict[str, Any],
    metadata_name: str,
    bucket: str = S3_BUCKET,
) -> str:
    cleaned_name = metadata_name.strip()
    if not cleaned_name:
        raise ValueError("metadata_name cannot be empty.")

    if not cleaned_name.endswith(".json"):
        cleaned_name = f"{cleaned_name}.json"

    payload = json.dumps(metadata, indent=2, ensure_ascii=False).encode("utf-8")
    return upload_bytes(
        s3_client=s3_client,
        data=payload,
        s3_key=cleaned_name,
        bucket=bucket,
        content_type="application/json",
    )


def download_model_file(
    s3_client,
    s3_key: str,
    local_path: str,
    bucket: str = S3_BUCKET,
) -> str:
    final_key = normalize_model_key(s3_key)
    output_path = Path(local_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    s3_client.download_file(
        Bucket=bucket,
        Key=final_key,
        Filename=str(output_path),
    )

    return str(output_path)


def get_object_bytes(
    s3_client,
    s3_key: str,
    bucket: str = S3_BUCKET,
) -> bytes:
    final_key = normalize_model_key(s3_key)
    response = s3_client.get_object(Bucket=bucket, Key=final_key)
    return response["Body"].read()


def load_pickle_model(
    s3_client,
    s3_key: str,
    bucket: str = S3_BUCKET,
) -> Any:
    payload = get_object_bytes(s3_client=s3_client, s3_key=s3_key, bucket=bucket)
    return pickle.loads(payload)


def read_json_metadata(
    s3_client,
    s3_key: str,
    bucket: str = S3_BUCKET,
) -> Dict[str, Any]:
    payload = get_object_bytes(s3_client=s3_client, s3_key=s3_key, bucket=bucket)
    return json.loads(payload.decode("utf-8"))


def list_model_objects(
    s3_client,
    prefix: str = MODEL_PREFIX,
    bucket: str = S3_BUCKET,
) -> List[Dict[str, Any]]:
    final_prefix = MODEL_PREFIX if prefix == MODEL_PREFIX else normalize_model_key(prefix)
    paginator = s3_client.get_paginator("list_objects_v2")

    results: List[Dict[str, Any]] = []

    for page in paginator.paginate(Bucket=bucket, Prefix=final_prefix):
        for obj in page.get("Contents", []):
            results.append(
                {
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                }
            )

    return results


def delete_model_object(
    s3_client,
    s3_key: str,
    bucket: str = S3_BUCKET,
) -> None:
    final_key = normalize_model_key(s3_key)
    s3_client.delete_object(Bucket=bucket, Key=final_key)


def object_exists(
    s3_client,
    s3_key: str,
    bucket: str = S3_BUCKET,
) -> bool:
    final_key = normalize_model_key(s3_key)
    try:
        s3_client.head_object(Bucket=bucket, Key=final_key)
        return True
    except Exception:
        return False