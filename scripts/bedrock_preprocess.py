"""
Bedrock Recipe Enrichment Test Script

Setup Steps
-----------

1. Install dependencies

pip install boto3

2. Run script

python bedrock_recipe_enrichment.py

3. When prompted, paste the AWS credential block exactly as provided
by AWS and press ENTER twice.
"""

import json
import os
import boto3
import configparser

from io import StringIO
from botocore.config import Config


# ----------------------------
# Configuration
# ----------------------------

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "amazon.nova-micro-v1:0"
)


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
        region_name=AWS_REGION
    )

    return session.client(
        service_name="bedrock-runtime",
        config=Config(read_timeout=3600)
    )


bedrock = build_bedrock_client()


# ----------------------------
# Prompt builders
# ----------------------------

def build_system_prompt():

    return """
You are a food recipe enrichment engine.

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
}
"""


def build_user_prompt(recipe):

    return f"""
Classify this recipe.

Recipe:

{json.dumps(recipe, indent=2)}
"""


# ----------------------------
# Bedrock call
# ----------------------------

def call_bedrock(recipe):

    response = bedrock.converse(
        modelId=MODEL_ID,
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
            "temperature": 0,
            "maxTokens": 1000
        },
    )

    output_text = response["output"]["message"]["content"][0]["text"]

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError:
        print("\nRaw response from model:\n")
        print(output_text)
        raise

    return parsed


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
        "curry powder"
    ],

    "instructions": [
        "Saute onion and garlic.",
        "Add curry powder.",
        "Add chickpeas and coconut milk.",
        "Simmer for 20 minutes."
    ],

    "nutrition_summary": {
        "calories": 420,
        "protein_g": 15,
        "fat_g": 18,
        "carbs_g": 38
    },

    "prep_time": 10,
    "cook_time": 20,
    "total_time": 30,

    "review_summary": [
        "This recipe was delicious and easy to make.",
        "Great weeknight dinner.",
        "Flavorful and simple."
    ]
}


# ----------------------------
# Main
# ----------------------------

if __name__ == "__main__":

    print("\nSending recipe to Bedrock...\n")

    result = call_bedrock(dummy_recipe)

    print("Enriched Recipe Output\n")

    print(json.dumps(result, indent=2))