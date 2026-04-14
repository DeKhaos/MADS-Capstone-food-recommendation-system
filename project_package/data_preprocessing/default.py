"""
This module store default variables
"""

# Default column name in Dataset object --------------------------------------------------------------------
USER = "user_id"
ITEM = "recipe_id"
RATING_COL = "rating"
TIME_COL = "modified_time"

# Mapping names and columns to use from raw dataset --------------------------------------------------------------
RECIPE_TO_USE = [
    "RecipeId","source","Name","RecipeInstructions","Calories",
    "ingredients_canonical_final_le_5_replace",
    "PrepTime_Minutes",
    "CookTime_Minutes","TotalTime_Minutes",
    "WHO_Score","FSA_Score"

]
REVIEW_TO_USE = [
    "AuthorId","RecipeId","source","Rating","DateModified"
]

RECIPE_COLUMN_MAPPING = {
    "RecipeId":"original_id",
    "Name":"recipe_name",
    "RecipeInstructions":"instructions",
    "Calories":"calories",
    "ingredients_canonical_final_le_5_replace":"ingredients",
    "PrepTime_Minutes":"prep_time",
    "CookTime_Minutes":"cook_time",
    "TotalTime_Minutes":"total_time",
    "WHO_Score":"who_score",
    "FSA_Score":"fsa_score"
}

REVIEW_COLUMN_MAPPING = {
    "RecipeId":"original_id",
    "AuthorId":"original_user_id",
    "Rating":"rating",
    "DateModified":"modified_time"
}

# Identify all to-use features and category features for Rectool Dataset generation -------------------------------

ITEM_ALL_FEATURES = [
    'calories','prep_time', 'cook_time', 'total_time', 'ingredients', 'who_score',
    'fsa_score', 'cuisine', 'cooking_method', 'difficulty',
    'protein_content', 'fiber_content', 'fat_content',
    'carbohydrate_content', 'sodium_content'
]
ITEM_CAT_FEATURES = [
    'ingredients', 'cuisine', 'cooking_method', 'difficulty',
    'protein_content', 'fiber_content', 'fat_content',
    'carbohydrate_content', 'sodium_content'
]
EXPLODE_ITEM_FEATURES = ['ingredients','cooking_method']  # features that have a collection as its value
USER_CAT_FEATURES = [
    'ingredients','cuisine','cooking_method','difficulty','protein_content',
    'fiber_content','fat_content','carbohydrate_content','sodium_content'
]
EXPLODE_USER_FEATURES = [
    'ingredients','cuisine','cooking_method','difficulty','protein_content',
    'fiber_content','fat_content','carbohydrate_content','sodium_content'
]  # features that have a collection as its value

#CHROMA vectorstore to-use variables and templates --------------------------------------------------------------

DOC_TEMPLATE = """
The recipe name:{}.
Recipe instruction:
{}
Ingredient list:
{}
Cuisine:{}
Cooking method:{}
The difficulty is {}.
Protein content is {}.
Fiber content is {}.
Fat content is {}.
Carbohydrate content is {}.
Sodium content is {}.
"""

USER_PROFILE_TEMPLATE = """
Favorite ingredients are: {}.
Favorite cuisine are: {}.
Preferred cooking method: {}.
Preferred cooking difficulty: {}.
Preferred Protein content is {}.
Preferred Fiber content is {}.
Preferred Fat content is {}.
Preferred Carbohydrate content is {}.
Preferred Sodium content is {}.
"""

RECIPE_COLS = [
    'recipe_name','instructions','ingredients','cuisine','cooking_method',
    'difficulty','protein_content','fiber_content','fat_content','carbohydrate_content',
    'sodium_content'
]

RECIPE_META_COLS = [
    'recipe_id','ingredients','cuisine','cooking_method',
    'difficulty','protein_content','fiber_content','fat_content','carbohydrate_content',
    'sodium_content','calories','prep_time', 'cook_time', 'total_time','who_score',
    'fsa_score'
]

PREFERENCE_COLS = [
    'ingredients',
    'cuisine',
    'cooking_method',
    'difficulty',
    'protein_content',
    'fiber_content',
    'fat_content',
    'carbohydrate_content',
    'sodium_content'
]

# DEFAULT FOR TESTING PURPOSE  --------------------------------------------------------------

USER_ML = "userId"
ITEM_ML = "movieId"
RATING_ML_COL = "rating"

ML_ITEM_ALL_FEATURES = ["genres","original_language","adult","runtime"]
ML_ITEM_CAT_FEATURES = ["genres","original_language","adult"]
EXPLODE_ML_ITEM_FEATURES = ["genres"]  # features that have a collection as its value
ML_USER_CAT_FEATURES = ["genres","original_language","adult"]
EXPLODE_ML_USER_FEATURES = ["genres","original_language","adult"]  # features that have a collection as its value