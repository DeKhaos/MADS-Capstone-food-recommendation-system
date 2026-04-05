import math
from typing import List, Optional


def score_time(total_time_minutes: Optional[float]) -> float:
    """
    More total time means higher difficulty.
    Returns a score from 0 to 40.
    """
    if total_time_minutes is None or total_time_minutes <= 0:
        return 0.0

    if total_time_minutes <= 15:
        return 5
    elif total_time_minutes <= 30:
        return 10
    elif total_time_minutes <= 45:
        return 18
    elif total_time_minutes <= 60:
        return 25
    elif total_time_minutes <= 90:
        return 32
    else:
        return 40


def score_methods(cooking_methods: Optional[List[str]]) -> float:
    """
    More unique cooking methods means higher difficulty.
    Returns a score from 0 to 30.
    """
    if not cooking_methods:
        return 0.0

    unique_methods = {
        method.strip().lower()
        for method in cooking_methods
        if method and str(method).strip()
    }

    method_count = len(unique_methods)

    if method_count == 0:
        return 0.0
    elif method_count == 1:
        return 8
    elif method_count == 2:
        return 15
    elif method_count == 3:
        return 22
    elif method_count == 4:
        return 27
    else:
        return 30


def score_ingredients(ingredients: Optional[List[str]]) -> float:
    """
    More ingredients means higher difficulty.
    Returns a score from 0 to 30.
    """
    if not ingredients:
        return 0.0

    ingredient_count = len([
        ingredient for ingredient in ingredients
        if ingredient and str(ingredient).strip()
    ])

    if ingredient_count <= 5:
        return 5
    elif ingredient_count <= 8:
        return 10
    elif ingredient_count <= 12:
        return 16
    elif ingredient_count <= 16:
        return 22
    elif ingredient_count <= 20:
        return 27
    else:
        return 30


def classify_difficulty(score: float) -> str:
    """
    Converts numeric score into difficulty label.
    """
    if score < 30:
        return "beginner"
    elif score < 65:
        return "intermediate"
    return "advanced"


def compute_recipe_difficulty(
    total_time_minutes: Optional[float],
    cooking_methods: Optional[List[str]],
    ingredients: Optional[List[str]],
) -> dict:
    """
    Computes difficulty from:
    1. Total time
    2. Number of cooking methods
    3. Number of ingredients

    Reviews are intentionally excluded.
    """
    time_score = score_time(total_time_minutes)
    method_score = score_methods(cooking_methods)
    ingredient_score = score_ingredients(ingredients)

    raw_score = time_score + method_score + ingredient_score
    difficulty_score = round(max(0, min(100, raw_score)), 2)
    difficulty_label = classify_difficulty(difficulty_score)

    return {
        "time_score": time_score,
        "method_score": method_score,
        "ingredient_score": ingredient_score,
        "difficulty_score": difficulty_score,
        "difficulty_label": difficulty_label,
    }