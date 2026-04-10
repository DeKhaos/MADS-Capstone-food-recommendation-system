from __future__ import annotations

from typing import Any, Dict, Optional


NUTRITION_UNKNOWN = "unknown"
NUTRITION_LOW = "low"
NUTRITION_MEDIUM = "medium"
NUTRITION_HIGH = "high"

VALID_LABELS = {
    NUTRITION_UNKNOWN,
    NUTRITION_LOW,
    NUTRITION_MEDIUM,
    NUTRITION_HIGH,
}


def _to_float(value: Any) -> Optional[float]:
    """
    Safely convert a value to float.
    Returns None if the value is missing, blank, or invalid.
    """
    if value is None:
        return None

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_per_serving(value: Any, servings: Any) -> Optional[float]:
    """
    Convert a total nutrient amount into a per serving amount.
    If servings is missing or invalid, fall back to the raw value.
    """
    numeric_value = _to_float(value)
    numeric_servings = _to_float(servings)

    if numeric_value is None:
        return None

    if numeric_servings is None or numeric_servings <= 0:
        return numeric_value

    return numeric_value / numeric_servings


def classify_protein_grams(value_per_serving: Any) -> str:
    """
    Protein classification, grams per serving.
    """
    x = _to_float(value_per_serving)
    if x is None:
        return NUTRITION_UNKNOWN
    if x < 10:
        return NUTRITION_LOW
    if x < 20:
        return NUTRITION_MEDIUM
    return NUTRITION_HIGH


def classify_fiber_grams(value_per_serving: Any) -> str:
    """
    Fiber classification, grams per serving.
    """
    x = _to_float(value_per_serving)
    if x is None:
        return NUTRITION_UNKNOWN
    if x < 3:
        return NUTRITION_LOW
    if x < 7:
        return NUTRITION_MEDIUM
    return NUTRITION_HIGH


def classify_fat_grams(value_per_serving: Any) -> str:
    """
    Fat classification, grams per serving.
    """
    x = _to_float(value_per_serving)
    if x is None:
        return NUTRITION_UNKNOWN
    if x < 8:
        return NUTRITION_LOW
    if x < 17.5:
        return NUTRITION_MEDIUM
    return NUTRITION_HIGH


def classify_carbohydrate_grams(value_per_serving: Any) -> str:
    """
    Carbohydrate classification, grams per serving.
    """
    x = _to_float(value_per_serving)
    if x is None:
        return NUTRITION_UNKNOWN
    if x < 15:
        return NUTRITION_LOW
    if x < 30:
        return NUTRITION_MEDIUM
    return NUTRITION_HIGH


def classify_sodium_mg(value_per_serving: Any) -> str:
    """
    Sodium classification, milligrams per serving.
    """
    x = _to_float(value_per_serving)
    if x is None:
        return NUTRITION_UNKNOWN
    if x < 140:
        return NUTRITION_LOW
    if x < 400:
        return NUTRITION_MEDIUM
    return NUTRITION_HIGH


def build_nutrition_labels(
    recipe: Dict[str, Any],
    *,
    servings_key: str = "RecipeServings_fill",
    protein_key: str = "ProteinContent",
    fiber_key: str = "FiberContent",
    fat_key: str = "FatContent",
    carbohydrate_key: str = "CarbohydrateContent",
    sodium_key: str = "SodiumContent",
    use_per_serving: bool = True,
) -> Dict[str, str]:
    """
    Build nutrition labels for a single recipe dictionary.

    Expected source columns are based on your current dataset, for example:
    ProteinContent, FiberContent, FatContent, CarbohydrateContent, SodiumContent,
    and RecipeServings_fill.

    Returns a dictionary with the final enum values:
    protein_content, fiber_content, fat_content, carbohydrate_content, sodium_content
    """
    servings = recipe.get(servings_key)

    if use_per_serving:
        protein_value = _safe_per_serving(recipe.get(protein_key), servings)
        fiber_value = _safe_per_serving(recipe.get(fiber_key), servings)
        fat_value = _safe_per_serving(recipe.get(fat_key), servings)
        carbohydrate_value = _safe_per_serving(recipe.get(carbohydrate_key), servings)
        sodium_value = _safe_per_serving(recipe.get(sodium_key), servings)
    else:
        protein_value = _to_float(recipe.get(protein_key))
        fiber_value = _to_float(recipe.get(fiber_key))
        fat_value = _to_float(recipe.get(fat_key))
        carbohydrate_value = _to_float(recipe.get(carbohydrate_key))
        sodium_value = _to_float(recipe.get(sodium_key))

    return {
        "protein_content": classify_protein_grams(protein_value),
        "fiber_content": classify_fiber_grams(fiber_value),
        "fat_content": classify_fat_grams(fat_value),
        "carbohydrate_content": classify_carbohydrate_grams(carbohydrate_value),
        "sodium_content": classify_sodium_mg(sodium_value),
    }


def add_nutrition_labels_to_recipe(
    recipe: Dict[str, Any],
    *,
    inplace: bool = False,
    servings_key: str = "RecipeServings_fill",
    protein_key: str = "ProteinContent",
    fiber_key: str = "FiberContent",
    fat_key: str = "FatContent",
    carbohydrate_key: str = "CarbohydrateContent",
    sodium_key: str = "SodiumContent",
    use_per_serving: bool = True,
) -> Dict[str, Any]:
    """
    Add nutrition classification labels directly onto a recipe JSON object.

    By default this returns a new dictionary.
    Set inplace=True if you want to mutate the original object.
    """
    target = recipe if inplace else dict(recipe)

    labels = build_nutrition_labels(
        recipe,
        servings_key=servings_key,
        protein_key=protein_key,
        fiber_key=fiber_key,
        fat_key=fat_key,
        carbohydrate_key=carbohydrate_key,
        sodium_key=sodium_key,
        use_per_serving=use_per_serving,
    )

    target.update(labels)
    return target


def prepare_recipe_for_rds(recipe: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience wrapper for your current dataset structure.

    This adds:
    protein_content
    fiber_content
    fat_content
    carbohydrate_content
    sodium_content

    onto the JSON object so it can be stored in your RDS recipes table.
    """
    return add_nutrition_labels_to_recipe(
        recipe,
        inplace=False,
        servings_key="RecipeServings_fill",
        protein_key="ProteinContent",
        fiber_key="FiberContent",
        fat_key="FatContent",
        carbohydrate_key="CarbohydrateContent",
        sodium_key="SodiumContent",
        use_per_serving=True,
    )