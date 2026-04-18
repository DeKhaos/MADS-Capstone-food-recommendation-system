"""
This module hold all precalculated variables to be used for Dash application.They are all stored in memory.
We can also add a logic to access them from a different file storage later
"""
import os
from pathlib import Path

from flashrank import Ranker
from rectools.models import load_model

from project_package.modeling.recommendation_utils import get_embedding_model,load_vector_store
from ..data_preprocessing.resource_access import (
    load_preference_data,load_user_review_data,load_recipe_data,construct_rec_train_dataset
    )

_app_data = {
    "embedding_model":None,
    "vectorstore":None,
    "user_vectorstore":None,
    "recipe_df":None,
    "user_reviews":None,
    "preference_df":None,
    "dataset":None,
    "item-content":None,
    "collab":None,
    "hybrid":None,
    "reranker":None,
    "chunk_test": False
}

root_directory = Path(os.getcwd())
full_data = os.environ.get('IN_MEMORY_DATA','full')

# Chroma vectorstore
embedding_model = get_embedding_model(
    huggingface_model_path="BAAI/bge-small-en-v1.5",
    local_model_name="bge-small",
    device=os.environ.get("DEVICE","cpu")
)
chroma_path = root_directory / "data/processed/chroma_db"

vectorstore = load_vector_store(
        collection_name="recipe_collection",
        embedding_model=embedding_model,
        persist_directory=chroma_path
    )
user_vectorstore = load_vector_store(
        collection_name="user_recipe_preference",
        embedding_model=embedding_model,
        persist_directory=chroma_path
    )

# Data for model to create recommendation
recipe_df = load_recipe_data(root_directory, full_data!="full")
user_reviews = load_user_review_data(root_directory,recipe_df, full_data!="full")
preference_df = load_preference_data(root_directory,recipe_df,user_reviews)
if full_data!="full":  # for chunk test, need to reduce to include only user used in chunk model
    preference_df = preference_df.loc[
        preference_df["user_id"].isin(user_reviews["user_id"].unique())
        ].reset_index(drop=True)

dataset = construct_rec_train_dataset(
    user_reviews,
    recipe_df,
    preference_df,
    use_datetime = True
)

#Reranker model
reranker = Ranker(
    model_name="ms-marco-MiniLM-L-12-v2",  # NOTE: Can change to a different Flashrank model of your liking
    cache_dir=os.environ["FLASHRANK_PATH"]
)

# Recommendation models
#NOTE: Load the models, for big model, we might need to load this from S3 or google drive
svd_model = load_model(root_directory / "models/recommendation_models/svd_recommendation_model.pkl")
lightfm_model = load_model(root_directory / "models/recommendation_models/lightFM_recommendation_model.pkl")


# write to _app_data for easy access in UI app
_app_data['embedding_model'] = embedding_model
_app_data['vectorstore'] = vectorstore
_app_data['user_vectorstore'] = user_vectorstore
_app_data['recipe_df'] = recipe_df
_app_data['user_reviews'] = user_reviews
_app_data['preference_df'] = preference_df
_app_data['dataset'] = dataset
_app_data['collab'] = svd_model
_app_data['hybrid'] = lightfm_model
_app_data['reranker'] = reranker

if full_data!="full":
    _app_data["chunk_test"] = True

