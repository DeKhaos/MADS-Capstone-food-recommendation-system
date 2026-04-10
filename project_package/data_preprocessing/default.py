"""
This module store default variables
"""

# Default column name in dataset
USER = "UserId"
ITEM = "RecipeId"
RATING_COL = "Rating"
RATING_ID = "ReviewId"

ITEM_CAT_FEATURES = []
USER_CAT_FEATURES = []
EXPLODE_ITEM_FEATURES = []  # features that have a collection as its value
EXPLODE_USER_FEATURES = []  # features that have a collection as its value



# DEFAULT FOR TESTING PURPOSE

USER_ML = "userId"
ITEM_ML = "movieId"
RATING_ML_COL = "rating"


ML_ITEM_CAT_FEATURES = ["genres","original_language","adult","runtime"]
ML_USER_CAT_FEATURES = ["genres","original_language","adult"]
EXPLODE_ML_ITEM_FEATURES = ["genres"]  # features that have a collection as its value
EXPLODE_ML_USER_FEATURES = ["genres","original_language","adult"]  # features that have a collection as its value