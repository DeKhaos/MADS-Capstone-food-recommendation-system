"""
Bedrock Recipe Enrichment Model Comparison Script

What it does
------------
1. Prompts for temporary AWS credentials in [default] format
2. Runs the same recipe enrichment task on:
   * Amazon Nova Micro
   * Anthropic Claude 3.5 Haiku
   * Meta Llama 3.2 11B Instruct
3. Tests each model at temperatures:
   * 0.1
   * 0.3
   * 0.5
4. Scores each response on:
   * valid JSON
   * schema validity
   * selected field accuracy
   * latency
5. Estimates per-run cost from token usage
6. Reports:
   * best quality run
   * best value run, cheapest run that still meets quality thresholds
7. Saves detailed and summary CSVs

Install
-------
pip install boto3

Run
---
python bedrock_compare_recipe_models.py
"""

import csv
import json
import os
import time
import configparser
from io import StringIO

import boto3
from botocore.config import Config


# ----------------------------
# Configuration
# ----------------------------

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Fill these with current AWS Bedrock prices for your region and tier.
# Nova Micro values below are verified from AWS Nova pricing.
# Claude and Llama values should be updated from the AWS Bedrock pricing page.
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

REQUIRED_FIELDS = [
    "recipe_id",
    "cuisine",
    "meal_type",
    "dietary_tags",
    "allergens",
    "cooking_methods",
    "main_protein",
    "protein_level",
    "health_profile",
    "difficulty",
    "review_sentiment",
    "review_quality",
    "review_themes",
    "occasion_tags",
    "taste",
]

ALLOWED_PROTEIN_LEVELS = {"High Protein", "Moderate Protein", "Low Protein", "Unknown"}
ALLOWED_DIFFICULTY = {"Easy", "Medium", "Advanced"}
ALLOWED_REVIEW_SENTIMENT = {"Positive", "Mixed", "Negative"}
ALLOWED_REVIEW_QUALITY = {"Highly Reviewed", "Mixed Reception", "Poorly Reviewed"}

# Weighted ranking
WEIGHTS = {
    "valid_json": 20,
    "valid_schema": 20,
    "field_accuracy": 50,
    "latency_bonus": 10,
}

# Quality gates for "best value"
MIN_OVERALL_SCORE = 85.0
MIN_FIELD_ACCURACY = 0.75
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

    credential_text = "\n".join(lines)

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

Anti-leakage rules:
Reviews may only be used for:
difficulty
review_sentiment
review_quality
review_themes
occasion_tags
taste

Reviews must NOT be used for:
cuisine
dietary_tags
allergens
cooking_methods
health_profile
protein_level
fiber_level

Important classification rules:

1. Use only structured recipe content such as title, ingredients, instructions, and nutrition fields for cuisine, dietary_tags, allergens, cooking_methods, health_profile, protein_level, and fiber related classification.

2. If nutrition data includes protein in grams, classify protein_level using these exact thresholds:
   High Protein = protein_g >= 30
   Moderate Protein = protein_g > 10 and protein_g < 30
   Low Protein = protein_g <= 10

3. If nutrition data includes fiber in grams, add one of the following fiber indicators to health_profile:
   High Fiber = fiber_g >= 8
   Moderate Fiber = fiber_g > 3 and fiber_g < 8
   Low Fiber = fiber_g <= 3

4. Do not guess protein_level or fiber classification from reviews.

5. If protein or fiber data is missing, infer cautiously from ingredients only when strongly supported. If not strongly supported, return an empty value or omit that specific label.

6. health_profile should reflect nutrition oriented tags only, such as:
   ["High Protein", "Moderate Protein", "Low Protein", "High Fiber", "Moderate Fiber", "Low Fiber", "sour", "Low Carb", "Low Fat", "Calorie Dense", "Balanced"]

7. taste should reflect one of the following tags:
   ["spicy", "sweet", "bitter", "savory"]

Return JSON only.

Schema:
{
  "recipe_id": "string",
  "cuisine": ["string"],
  "meal_type": ["string"],
  "dietary_tags": ["string"],
  "allergens": ["string"],
  "cooking_methods": ["string"],
  "main_protein": ["string"],
  "protein_level": "High Protein|Moderate Protein|Low Protein|Unknown",
  "health_profile": ["string"],
  "difficulty": "Easy|Medium|Advanced",
  "review_sentiment": "Positive|Mixed|Negative",
  "review_quality": "Highly Reviewed|Mixed Reception|Poorly Reviewed",
  "review_themes": ["string"],
  "occasion_tags": ["string"],
  "taste": ["string"]
}"""


def build_user_prompt(recipe):
    return f"""Classify this recipe.

Recipe:
{json.dumps(recipe, indent=2)}"""


# ----------------------------
# Helpers
# ----------------------------

def normalize_str(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def normalize_list(value):
    if value is None:
        return []
    if not isinstance(value, list):
        return [normalize_str(value)]
    return sorted({normalize_str(x) for x in value if str(x).strip()})


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

    list_fields = [
        "cuisine",
        "meal_type",
        "dietary_tags",
        "allergens",
        "cooking_methods",
        "main_protein",
        "health_profile",
        "review_themes",
        "occasion_tags",
        "taste",
    ]

    for field in list_fields:
        if not is_list_of_strings(obj.get(field)):
            errors.append(f"{field} must be a list of strings")

    if not isinstance(obj.get("recipe_id"), str):
        errors.append("recipe_id must be a string")

    if obj.get("protein_level") not in ALLOWED_PROTEIN_LEVELS:
        errors.append("protein_level has invalid value")

    if obj.get("difficulty") not in ALLOWED_DIFFICULTY:
        errors.append("difficulty has invalid value")

    if obj.get("review_sentiment") not in ALLOWED_REVIEW_SENTIMENT:
        errors.append("review_sentiment has invalid value")

    if obj.get("review_quality") not in ALLOWED_REVIEW_QUALITY:
        errors.append("review_quality has invalid value")

    return len(errors) == 0, errors


def compare_field(pred, expected, field):
    if field not in expected:
        return None

    pred_val = pred.get(field)
    exp_val = expected[field]

    if isinstance(exp_val, list):
        pred_set = set(normalize_list(pred_val))
        exp_set = set(normalize_list(exp_val))

        if not exp_set and not pred_set:
            return 1.0
        if not exp_set:
            return 1.0

        intersection = len(pred_set & exp_set)
        union = len(pred_set | exp_set)
        return intersection / union if union else 1.0

    return 1.0 if normalize_str(pred_val) == normalize_str(exp_val) else 0.0


def compute_accuracy(pred, expected):
    fields_to_score = [
        "recipe_id",
        "protein_level",
        "difficulty",
        "review_sentiment",
        "review_quality",
        "taste",
        "cuisine",
        "meal_type",
        "dietary_tags",
        "cooking_methods",
        "main_protein",
        "health_profile",
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
# Dummy test data
# ----------------------------

dummy_recipe = {
    "recipe_id": "1024",
    "title": "Spicy Chickpea Curry",
    "ingredients_canonical": [
        "chickpeas",
        "onion",
        "garlic",
        "coconut milk",
        "curry powder",
    ],
    "instructions": [
        "Saute onion and garlic.",
        "Add curry powder.",
        "Add chickpeas and coconut milk.",
        "Simmer for 20 minutes.",
    ],
    "nutrition_summary": {
        "calories": 420,
        "protein_g": 15,
        "fat_g": 18,
        "carbs_g": 38,
    },
    "prep_time": 10,
    "cook_time": 20,
    "total_time": 30,
    "review_summary": [
        "This recipe was delicious and easy to make.",
        "Great weeknight dinner.",
        "Flavorful and simple.",
    ],
}

expected_output = {
    "recipe_id": "1024",
    "cuisine": ["Indian"],
    "meal_type": ["Dinner"],
    "dietary_tags": ["Vegetarian"],
    "allergens": ["Tree Nuts"],
    "cooking_methods": ["Saute", "Simmer"],
    "main_protein": ["Chickpeas"],
    "protein_level": "Moderate Protein",
    "health_profile": ["Moderate Protein", "Balanced"],
    "difficulty": "Easy",
    "review_sentiment": "Positive",
    "review_quality": "Highly Reviewed",
    "review_themes": ["easy", "flavorful", "weeknight meal"],
    "occasion_tags": ["Weeknight Dinner"],
    "taste": ["spicy", "savory"],
}


# ----------------------------
# Main
# ----------------------------

if __name__ == "__main__":
    print(f"\nUsing AWS region: {AWS_REGION}\n")
    bedrock = build_bedrock_client()

    detailed_rows = []

    print("Running model comparison...\n")

    for model in MODELS:
        for temperature in TEMPERATURES:
            model_label = model["label"]
            model_id = model["model_id"]

            print(f"Testing: {model_label} | {model_id} | temperature={temperature}")

            try:
                result = call_bedrock(
                    bedrock=bedrock,
                    model_id=model_id,
                    recipe=dummy_recipe,
                    temperature=temperature,
                )

                parsed = result.get("parsed")
                valid_json = result["valid_json"]

                valid_schema = False
                schema_errors = []
                field_accuracy = 0.0
                field_scores = {}

                if valid_json and isinstance(parsed, dict):
                    valid_schema, schema_errors = validate_schema(parsed)
                    field_accuracy, field_scores = compute_accuracy(parsed, expected_output)

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
                    "overall_score": total_score,
                    "schema_errors": " | ".join(schema_errors) if schema_errors else "",
                    "field_scores_json": json.dumps(field_scores),
                    "raw_output": result.get("raw_text", ""),
                    "parsed_output": json.dumps(parsed, ensure_ascii=False) if parsed is not None else "",
                    "error": "",
                }

                print(
                    f"  valid_json={valid_json}, "
                    f"valid_schema={valid_schema}, "
                    f"field_accuracy={field_accuracy:.3f}, "
                    f"latency={result['latency_sec']:.2f}s, "
                    f"cost=${run_cost:.8f}, "
                    f"score={total_score:.2f}\n"
                )

            except Exception as e:
                row = {
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
                    "overall_score": 0.0,
                    "schema_errors": "",
                    "field_scores_json": "{}",
                    "raw_output": "",
                    "parsed_output": "",
                    "error": str(e),
                }

                print(f"  FAILED: {e}\n")

            detailed_rows.append(row)

    valid_rows = [r for r in detailed_rows if r.get("error", "") == ""]

    # Rank all runs by quality
    ranked = sorted(valid_rows, key=lambda x: x["overall_score"], reverse=True)

    print("\n=== Ranked Results by Quality ===\n")
    for i, row in enumerate(ranked, start=1):
        print(
            f"{i}. {row['model_label']} | temp={row['temperature']} | "
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
            "overall_score": best_quality["overall_score"],
            "field_accuracy": best_quality["field_accuracy"],
            "latency_sec": best_quality["latency_sec"],
            "run_cost_usd": best_quality["run_cost_usd"],
        }, indent=2))

    if best_value:
        print("\n=== Best Value Candidate, cheapest acceptable quality ===\n")
        print(json.dumps({
            "model_label": best_value["model_label"],
            "model_id": best_value["model_id"],
            "temperature": best_value["temperature"],
            "overall_score": best_value["overall_score"],
            "field_accuracy": best_value["field_accuracy"],
            "latency_sec": best_value["latency_sec"],
            "run_cost_usd": best_value["run_cost_usd"],
        }, indent=2))

    # Save detailed CSV
    detail_fieldnames = [
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
        "overall_score",
        "schema_errors",
        "field_scores_json",
        "raw_output",
        "parsed_output",
        "error",
    ]

    with open(DETAIL_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=detail_fieldnames)
        writer.writeheader()
        writer.writerows(detailed_rows)

    # Save summary CSV
    summary_rows = []
    grouped = {}

    for row in valid_rows:
        key = (row["model_label"], row["model_id"])
        grouped.setdefault(key, []).append(row)

    for (model_label, model_id), rows in grouped.items():
        avg_score = sum(r["overall_score"] for r in rows) / len(rows)
        avg_accuracy = sum(r["field_accuracy"] for r in rows) / len(rows)
        avg_latency = sum(r["latency_sec"] for r in rows) / len(rows)
        avg_cost = sum(r["run_cost_usd"] for r in rows) / len(rows)

        best_row = max(rows, key=lambda r: r["overall_score"])

        summary_rows.append({
            "model_label": model_label,
            "model_id": model_id,
            "avg_overall_score": round(avg_score, 4),
            "avg_field_accuracy": round(avg_accuracy, 4),
            "avg_latency_sec": round(avg_latency, 4),
            "avg_run_cost_usd": round(avg_cost, 8),
            "value_index": round(avg_score / avg_cost, 4) if avg_cost > 0 else "",
            "best_temperature": best_row["temperature"],
            "best_single_run_score": best_row["overall_score"],
            "best_single_run_cost_usd": best_row["run_cost_usd"],
        })

    summary_rows = sorted(summary_rows, key=lambda x: x["avg_overall_score"], reverse=True)

    summary_fieldnames = [
        "model_label",
        "model_id",
        "avg_overall_score",
        "avg_field_accuracy",
        "avg_latency_sec",
        "avg_run_cost_usd",
        "value_index",
        "best_temperature",
        "best_single_run_score",
        "best_single_run_cost_usd",
    ]

    with open(SUMMARY_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nDetailed results written to: {DETAIL_CSV}")
    print(f"Summary results written to: {SUMMARY_CSV}")