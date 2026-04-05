"""
Bedrock Recipe Enrichment Model Comparison Script
JSON driven version for the new schema.

What it does
------------
1. Prompts for temporary AWS credentials in [default] format
2. Reads labeled evaluation records from a JSON file
3. Runs the same recipe enrichment task on multiple Bedrock models
4. Tests each model at multiple temperatures
5. Scores each response on:
   * valid JSON
   * valid schema
   * field accuracy against labeled rows
   * latency
6. Estimates per run cost from token usage
7. Saves detailed and summary CSVs

Install
-------
pip install boto3

Run
---
python model_comparisons.py
"""

import json
import os
import time
import configparser
from io import StringIO
from typing import Any, Dict, List, Optional

import boto3
from botocore.config import Config


# ----------------------------
# Configuration
# ----------------------------

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
INPUT_JSON = "labeled_recipe_eval_inputs.json"

MODELS = [
    {
        "label": "Amazon Nova Micro",
        "model_id": "amazon.nova-micro-v1:0",
        "input_cost_per_1m": 0.035,
        "output_cost_per_1m": 0.14,
    },
    {
        "label": "Anthropic Claude 3.5 Haiku",
        "model_id": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
        "input_cost_per_1m": 0.80,
        "output_cost_per_1m": 4.00,
    },
    {
        "label": "Meta Llama 3.2 11B Instruct",
        "model_id": "us.meta.llama3-2-11b-instruct-v1:0",
        "input_cost_per_1m": 0.16,
        "output_cost_per_1m": 0.16,
    }
]

TEMPERATURES = [0.1, 0.3, 0.5]

DETAIL_CSV = "bedrock_recipe_model_results.csv"
SUMMARY_CSV = "bedrock_recipe_model_summary.csv"
INPUT_JSON = os.getenv("INPUT_JSON", "labeled_recipe_eval_inputs.json")
MAX_RECIPES = int(os.getenv("MAX_RECIPES", "0"))  # 0 means all

REQUIRED_FIELDS = [
    "recipe_id",
    "cuisine",
    "meal_type",
    "allergens",
    "cooking_methods",
]

# New schema allowed values
ALLOWED_CUISINES = {
    "asian",
    "european",
    "american",
    "african",
    "mediterranean",
    "fusion",
    # allow common labels found in human annotations
    "italian",
    "japanese",
    "chinese",
    "indian",
    "french",
    "german",
    "thai",
}

ALLOWED_MEAL_TYPES = {
    "breakfast",
    "lunch",
    "dinner",
    "dessert",
    "beverage",
    "beverages",
    # allow labels found in the uploaded annotations
    "side",
    "snack",
}

ALLOWED_ALLERGENS = {
    # prompt allowed set
    "celery",
    "gluten",
    "crustaceans",
    "eggs",
    "fish",
    "lupin",
    "milk",
    "molluscs",
    "mustard",
    "nuts",
    "peanuts",
    "sesame seeds",
    "sulphur dioxide",
    "soy",
    # allow annotation synonyms seen in the uploaded CSVs
    "wheat",
    "dairy",
    "grains",
    "shellfish",
    "seafood",
}

ALLOWED_COOKING_METHODS = {
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
}

WEIGHTS = {
    "valid_json": 20,
    "valid_schema": 20,
    "field_accuracy": 50,
    "latency_bonus": 10,
}

MIN_OVERALL_SCORE = 70.0
MIN_FIELD_ACCURACY = 0.50
REQUIRE_VALID_JSON = True
REQUIRE_VALID_SCHEMA = True


# ----------------------------
# Credential input
# ----------------------------

def get_credentials_from_block():
    print("\nPaste the AWS credential block exactly as provided.")
    print("Press ENTER twice when finished.\n")

    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    credential_text = "\n".join(lines).strip()

    if not credential_text:
        raise ValueError("No credential block was provided.")

    parser = configparser.ConfigParser()
    parser.read_file(StringIO(credential_text))

    if "default" not in parser:
        raise ValueError("Credential block must contain [default] profile")

    profile = parser["default"]
    access_key = profile.get("aws_access_key_id")
    secret_key = profile.get("aws_secret_access_key")
    session_token = profile.get("aws_session_token")

    if not access_key or not secret_key:
        raise ValueError("Missing aws_access_key_id or aws_secret_access_key")

    return access_key, secret_key, session_token


def build_bedrock_client():
    access_key, secret_key, session_token = get_credentials_from_block()

    session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
        region_name=AWS_REGION,
    )

    return session.client(
        service_name="bedrock-runtime",
        config=Config(read_timeout=3600),
    )


# ----------------------------
# Prompt builders
# ----------------------------

def build_system_prompt():
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

2. meal_type should be limited to either breakfast, lunch, dinner, dessert and beverages.

3. allergens should be limited to celery, gluten, crustaceans, eggs, fish, lupin, milk, molluscs, mustard, nuts, peanuts, sesame seeds, sulphur dioxide and soy

Return JSON only.

Schema:

{
  "recipe_id": "string",
  "cuisine": ["string"],
  "meal_type": ["string"],
  "allergens": ["string"],
  "cooking_methods": ["string"]
}"""


def build_user_prompt(recipe):
    return f"""Classify this recipe.

Recipe:
{json.dumps(recipe, ensure_ascii=False, indent=2)}"""


# ----------------------------
# Helpers
# ----------------------------

def normalize_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def canonicalize_cuisine(value: str) -> str:
    x = normalize_str(value)
    mapping = {
        "american": "american",
        "asian": "asian",
        "african": "african",
        "mediterranean": "mediterranean",
        "fusion": "fusion",
        "italian": "european",
        "french": "european",
        "german": "european",
        "japanese": "asian",
        "chinese": "asian",
        "indian": "asian",
        "thai": "asian",
        "european": "european",
    }
    return mapping.get(x, x)


def canonicalize_meal_type(value: str) -> str:
    x = normalize_str(value)
    mapping = {
        "beverages": "beverage",
        "beverage": "beverage",
        "side": "snack",
    }
    return mapping.get(x, x)


def canonicalize_allergen(value: str) -> str:
    x = normalize_str(value)
    mapping = {
        "dairy": "milk",
        "wheat": "gluten",
        "grains": "gluten",
        "shell fish": "shellfish",
    }
    return mapping.get(x, x)


def canonicalize_cooking_method(value: str) -> str:
    x = normalize_str(value)
    mapping = {
        "saute": "sautee",
        "sauté": "sautee",
        "sous vide": "sous_vide",
    }
    return mapping.get(x, x)


def normalize_list(value: Any, field: Optional[str] = None) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        values = value
    else:
        values = [value]

    cleaned = []
    seen = set()

    for item in values:
        text = normalize_str(item)
        if not text:
            continue

        if field == "cuisine":
            text = canonicalize_cuisine(text)
        elif field == "meal_type":
            text = canonicalize_meal_type(text)
        elif field == "allergens":
            text = canonicalize_allergen(text)
        elif field == "cooking_methods":
            text = canonicalize_cooking_method(text)

        if text not in seen:
            seen.add(text)
            cleaned.append(text)

    return cleaned


def extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        return json.loads(candidate)

    raise json.JSONDecodeError("No JSON object found", text, 0)


def is_list_of_strings(value):
    return isinstance(value, list) and all(isinstance(x, str) for x in value)


def validate_schema(obj):
    errors = []

    for field in REQUIRED_FIELDS:
        if field not in obj:
            errors.append(f"Missing field: {field}")

    if errors:
        return False, errors

    if not isinstance(obj.get("recipe_id"), str):
        errors.append("recipe_id must be a string")

    for field in ["cuisine", "meal_type", "allergens", "cooking_methods"]:
        if not is_list_of_strings(obj.get(field)):
            errors.append(f"{field} must be a list of strings")

    return len(errors) == 0, errors


def compare_field(pred, expected, field):
    if field not in expected:
        return None

    pred_val = normalize_list(pred.get(field), field=field) if field != "recipe_id" else normalize_str(pred.get(field))
    exp_val = normalize_list(expected.get(field), field=field) if field != "recipe_id" else normalize_str(expected.get(field))

    if field == "recipe_id":
        return 1.0 if pred_val == exp_val else 0.0

    pred_set = set(pred_val)
    exp_set = set(exp_val)

    if not exp_set and not pred_set:
        return 1.0
    if not exp_set:
        return 1.0

    intersection = len(pred_set & exp_set)
    union = len(pred_set | exp_set)
    return intersection / union if union else 1.0


def compute_accuracy(pred, expected):
    fields_to_score = [
        "recipe_id",
        "cuisine",
        "meal_type",
        "allergens",
        "cooking_methods",
    ]

    field_scores = {}
    used_scores = []

    for field in fields_to_score:
        score = compare_field(pred, expected, field)
        if score is not None:
            field_scores[field] = score
            used_scores.append(score)

    overall = sum(used_scores) / len(used_scores) if used_scores else 0.0
    return overall, field_scores


def compute_allowed_values_score(obj):
    checks = []
    errors = []

    cuisine = normalize_list(obj.get("cuisine"), field="cuisine")
    meal_type = normalize_list(obj.get("meal_type"), field="meal_type")
    allergens = normalize_list(obj.get("allergens"), field="allergens")
    cooking_methods = normalize_list(obj.get("cooking_methods"), field="cooking_methods")

    cuisine_ok = all(x in {"asian", "european", "american", "african", "mediterranean", "fusion"} for x in cuisine)
    meal_type_ok = all(x in {"breakfast", "lunch", "dinner", "dessert", "beverage", "snack"} for x in meal_type)
    allergens_ok = all(x in {
        "celery", "gluten", "crustaceans", "eggs", "fish", "lupin", "milk",
        "molluscs", "mustard", "nuts", "peanuts", "sesame seeds",
        "sulphur dioxide", "soy", "shellfish", "seafood"
    } for x in allergens)
    cooking_methods_ok = all(x in ALLOWED_COOKING_METHODS for x in cooking_methods)

    checks.extend([cuisine_ok, meal_type_ok, allergens_ok, cooking_methods_ok])

    if not cuisine_ok:
        errors.append("cuisine contains invalid values")
    if not meal_type_ok:
        errors.append("meal_type contains invalid values")
    if not allergens_ok:
        errors.append("allergens contains invalid values")
    if not cooking_methods_ok:
        errors.append("cooking_methods contains invalid values")

    score = sum(1 for x in checks if x) / len(checks) if checks else 0.0
    return round(score, 4), errors


def latency_bonus(latency_sec):
    return max(0.0, 1.0 - min(latency_sec, 20.0) / 20.0)


def overall_score(valid_json, valid_schema, field_accuracy, latency_sec):
    score = 0.0
    score += WEIGHTS["valid_json"] * (1.0 if valid_json else 0.0)
    score += WEIGHTS["valid_schema"] * (1.0 if valid_schema else 0.0)
    score += WEIGHTS["field_accuracy"] * field_accuracy
    score += WEIGHTS["latency_bonus"] * latency_bonus(latency_sec)
    return round(score, 4)


def compute_run_cost(input_tokens, output_tokens, input_cost_per_1m, output_cost_per_1m):
    input_tokens = input_tokens or 0
    output_tokens = output_tokens or 0

    input_cost = (input_tokens / 1_000_000) * input_cost_per_1m
    output_cost = (output_tokens / 1_000_000) * output_cost_per_1m

    return round(input_cost + output_cost, 8)


def choose_best_value_run(rows):
    acceptable_runs = [
        r for r in rows
        if r.get("error", "") == ""
        and (not REQUIRE_VALID_JSON or r["valid_json"] == 1)
        and (not REQUIRE_VALID_SCHEMA or r["valid_schema"] == 1)
        and r["overall_score"] >= MIN_OVERALL_SCORE
        and r["field_accuracy"] >= MIN_FIELD_ACCURACY
    ]

    if acceptable_runs:
        return min(
            acceptable_runs,
            key=lambda r: (r["run_cost_usd"], -r["overall_score"], r["latency_sec"])
        )

    valid_rows = [r for r in rows if r.get("error", "") == ""]
    if not valid_rows:
        return None

    return max(valid_rows, key=lambda r: (r["overall_score"], -r["run_cost_usd"]))


# ----------------------------
# JSON input loader
# ----------------------------

def load_eval_inputs(path: str, max_recipes: int = 0) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        rows = json.load(f)

    if not isinstance(rows, list):
        raise ValueError("Input JSON must contain a list of evaluation records")

    if max_recipes > 0:
        rows = rows[:max_recipes]

    return rows


# ----------------------------
# Bedrock call
# ----------------------------

def call_bedrock(bedrock, model_id, recipe, temperature):
    started = time.time()

    response = bedrock.converse(
        modelId=model_id,
        system=[{"text": build_system_prompt()}],
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": build_user_prompt(recipe)}
                ],
            }
        ],
        inferenceConfig={
            "temperature": temperature,
            "maxTokens": 1000,
        },
    )

    latency_sec = time.time() - started

    content_blocks = response["output"]["message"]["content"]
    output_text = "".join(block.get("text", "") for block in content_blocks if "text" in block)

    usage = response.get("usage", {})

    result = {
        "raw_text": output_text,
        "latency_sec": round(latency_sec, 4),
        "input_tokens": usage.get("inputTokens"),
        "output_tokens": usage.get("outputTokens"),
        "total_tokens": usage.get("totalTokens"),
        "stop_reason": response.get("stopReason"),
    }

    try:
        parsed = extract_json(output_text)
        result["parsed"] = parsed
        result["valid_json"] = True
    except Exception as e:
        result["parsed"] = None
        result["valid_json"] = False
        result["json_error"] = str(e)

    return result


# ----------------------------
# Main
# ----------------------------

if __name__ == "__main__":
    print(f"\nUsing AWS region: {AWS_REGION}\n")
    bedrock = build_bedrock_client()

    eval_rows = load_eval_inputs(INPUT_JSON, MAX_RECIPES)
    detailed_rows = []

    print(f"Loaded {len(eval_rows)} evaluation records from {INPUT_JSON}\n")
    print("Running model comparison...\n")

    for eval_row in eval_rows:
        recipe = eval_row["input"]
        expected_output = eval_row["expected_output"]
        recipe_id = eval_row["recipe_id"]
        source_file = eval_row.get("source_file", "")

        for model in MODELS:
            for temperature in TEMPERATURES:
                model_label = model["label"]
                model_id = model["model_id"]

                print(f"Testing: recipe_id={recipe_id} | {model_label} | temp={temperature}")

                try:
                    result = call_bedrock(
                        bedrock=bedrock,
                        model_id=model_id,
                        recipe=recipe,
                        temperature=temperature,
                    )

                    parsed = result.get("parsed")
                    valid_json = result["valid_json"]

                    valid_schema = False
                    schema_errors = []
                    field_accuracy = 0.0
                    field_scores = {}
                    allowed_values_score = 0.0
                    allowed_value_errors = []

                    if valid_json and isinstance(parsed, dict):
                        valid_schema, schema_errors = validate_schema(parsed)
                        field_accuracy, field_scores = compute_accuracy(parsed, expected_output)
                        allowed_values_score, allowed_value_errors = compute_allowed_values_score(parsed)

                    total_score = overall_score(
                        valid_json=valid_json,
                        valid_schema=valid_schema,
                        field_accuracy=field_accuracy,
                        latency_sec=result["latency_sec"],
                    )

                    input_tokens = result.get("input_tokens") or 0
                    output_tokens = result.get("output_tokens") or 0

                    run_cost = compute_run_cost(
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        input_cost_per_1m=model["input_cost_per_1m"],
                        output_cost_per_1m=model["output_cost_per_1m"],
                    )

                    row = {
                        "recipe_id": recipe_id,
                        "source_file": source_file,
                        "model_label": model_label,
                        "model_id": model_id,
                        "temperature": temperature,
                        "latency_sec": result["latency_sec"],
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": result.get("total_tokens"),
                        "run_cost_usd": run_cost,
                        "stop_reason": result.get("stop_reason"),
                        "valid_json": int(valid_json),
                        "valid_schema": int(valid_schema),
                        "field_accuracy": round(field_accuracy, 4),
                        "allowed_values_score": allowed_values_score,
                        "overall_score": total_score,
                        "schema_errors": " | ".join(schema_errors) if schema_errors else "",
                        "allowed_value_errors": " | ".join(allowed_value_errors) if allowed_value_errors else "",
                        "field_scores_json": json.dumps(field_scores),
                        "expected_output": json.dumps(expected_output, ensure_ascii=False),
                        "raw_output": result.get("raw_text", ""),
                        "parsed_output": json.dumps(parsed, ensure_ascii=False) if parsed is not None else "",
                        "error": "",
                    }

                    print(
                        f"  valid_json={valid_json}, "
                        f"valid_schema={valid_schema}, "
                        f"field_accuracy={field_accuracy:.3f}, "
                        f"allowed_values_score={allowed_values_score:.3f}, "
                        f"latency={result['latency_sec']:.2f}s, "
                        f"cost=${run_cost:.8f}, "
                        f"score={total_score:.2f}\n"
                    )

                except Exception as e:
                    row = {
                        "recipe_id": recipe_id,
                        "source_file": source_file,
                        "model_label": model_label,
                        "model_id": model_id,
                        "temperature": temperature,
                        "latency_sec": "",
                        "input_tokens": "",
                        "output_tokens": "",
                        "total_tokens": "",
                        "run_cost_usd": "",
                        "stop_reason": "",
                        "valid_json": 0,
                        "valid_schema": 0,
                        "field_accuracy": 0.0,
                        "allowed_values_score": 0.0,
                        "overall_score": 0.0,
                        "schema_errors": "",
                        "allowed_value_errors": "",
                        "field_scores_json": "{}",
                        "expected_output": json.dumps(expected_output, ensure_ascii=False),
                        "raw_output": "",
                        "parsed_output": "",
                        "error": str(e),
                    }

                    print(f"  FAILED: {e}\n")

                detailed_rows.append(row)

    valid_rows = [r for r in detailed_rows if r.get("error", "") == ""]

    ranked = sorted(valid_rows, key=lambda x: x["overall_score"], reverse=True)

    print("\n=== Ranked Results by Quality ===\n")
    for i, row in enumerate(ranked[:20], start=1):
        print(
            f"{i}. {row['model_label']} | recipe_id={row['recipe_id']} | temp={row['temperature']} | "
            f"score={row['overall_score']:.2f} | "
            f"field_accuracy={row['field_accuracy']:.3f} | "
            f"latency={row['latency_sec']:.2f}s | "
            f"cost=${row['run_cost_usd']:.8f}"
        )

    best_quality = ranked[0] if ranked else None
    best_value = choose_best_value_run(detailed_rows)

    if best_quality:
        print("\n=== Best Quality Candidate ===\n")
        print(json.dumps({
            "model_label": best_quality["model_label"],
            "model_id": best_quality["model_id"],
            "temperature": best_quality["temperature"],
            "recipe_id": best_quality["recipe_id"],
            "overall_score": best_quality["overall_score"],
            "field_accuracy": best_quality["field_accuracy"],
            "latency_sec": best_quality["latency_sec"],
            "run_cost_usd": best_quality["run_cost_usd"],
        }, indent=2))

    if best_value:
        print("\n=== Best Value Candidate ===\n")
        print(json.dumps({
            "model_label": best_value["model_label"],
            "model_id": best_value["model_id"],
            "temperature": best_value["temperature"],
            "recipe_id": best_value["recipe_id"],
            "overall_score": best_value["overall_score"],
            "field_accuracy": best_value["field_accuracy"],
            "latency_sec": best_value["latency_sec"],
            "run_cost_usd": best_value["run_cost_usd"],
        }, indent=2))

    detail_fieldnames = [
        "recipe_id",
        "source_file",
        "model_label",
        "model_id",
        "temperature",
        "latency_sec",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "run_cost_usd",
        "stop_reason",
        "valid_json",
        "valid_schema",
        "field_accuracy",
        "allowed_values_score",
        "overall_score",
        "schema_errors",
        "allowed_value_errors",
        "field_scores_json",
        "expected_output",
        "raw_output",
        "parsed_output",
        "error",
    ]

    import csv

    with open(DETAIL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=detail_fieldnames)
        writer.writeheader()
        writer.writerows(detailed_rows)

    summary_rows = []
    grouped = {}

    for row in valid_rows:
        key = (row["model_label"], row["model_id"])
        grouped.setdefault(key, []).append(row)

    for (model_label, model_id), rows in grouped.items():
        avg_score = sum(r["overall_score"] for r in rows) / len(rows)
        avg_accuracy = sum(r["field_accuracy"] for r in rows) / len(rows)
        avg_allowed = sum(r["allowed_values_score"] for r in rows) / len(rows)
        avg_latency = sum(r["latency_sec"] for r in rows) / len(rows)
        avg_cost = sum(r["run_cost_usd"] for r in rows) / len(rows)

        best_row = max(rows, key=lambda r: r["overall_score"])

        summary_rows.append({
            "model_label": model_label,
            "model_id": model_id,
            "avg_overall_score": round(avg_score, 4),
            "avg_field_accuracy": round(avg_accuracy, 4),
            "avg_allowed_values_score": round(avg_allowed, 4),
            "avg_latency_sec": round(avg_latency, 4),
            "avg_run_cost_usd": round(avg_cost, 8),
            "value_index": round(avg_score / avg_cost, 4) if avg_cost > 0 else "",
            "best_temperature": best_row["temperature"],
            "best_single_run_score": best_row["overall_score"],
            "best_single_run_cost_usd": best_row["run_cost_usd"],
            "recipes_evaluated": len(rows),
        })

    summary_rows = sorted(summary_rows, key=lambda x: x["avg_overall_score"], reverse=True)

    summary_fieldnames = [
        "model_label",
        "model_id",
        "avg_overall_score",
        "avg_field_accuracy",
        "avg_allowed_values_score",
        "avg_latency_sec",
        "avg_run_cost_usd",
        "value_index",
        "best_temperature",
        "best_single_run_score",
        "best_single_run_cost_usd",
        "recipes_evaluated",
    ]

    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nDetailed results written to: {DETAIL_CSV}")
    print(f"Summary results written to: {SUMMARY_CSV}")