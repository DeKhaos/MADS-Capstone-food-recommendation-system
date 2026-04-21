"""
This module hold all format function necessary to run the application and the modelling.
"""
import os
import ast
import glob
from pathlib import Path
from typing import Union

import pandas as pd
from rectools.dataset import Dataset

from ..aws.data_access import pandas_sql_df
from ..data_preprocessing.utils import create_user_preference

from .default import (
    USER,ITEM,RATING_COL,TIME_COL,
    ITEM_CAT_FEATURES,USER_CAT_FEATURES,EXPLODE_ITEM_FEATURES,EXPLODE_USER_FEATURES,
    ITEM_ALL_FEATURES,
    USER_ML,ITEM_ML,RATING_ML_COL,
    ML_ITEM_CAT_FEATURES,ML_USER_CAT_FEATURES,EXPLODE_ML_ITEM_FEATURES,EXPLODE_ML_USER_FEATURES,
    ML_ITEM_ALL_FEATURES,
    RECIPE_TO_USE,RECIPE_URL_TO_USE,RECIPE_COLUMN_MAPPING,RECIPE_META_COLS,REVIEW_TO_USE,REVIEW_COLUMN_MAPPING
)

def load_chunks(
        folder_path: str,
        file_syntax: str,
        usecols: list
    ):
    """combine chunks of csv file with same name syntax."""

    # Find all files matching file_syntax
    files = glob.glob(os.path.join(folder_path, file_syntax))
    files = sorted(files)

    # Load and concatenate
    df_list = [pd.read_csv(f,usecols=usecols) for f in files]
    combined_df = pd.concat(df_list, ignore_index=True)
    
    return combined_df

def load_recipe_data(
        root_directory: Union[Path,str],
        first_chunk_only: bool = False
    ):
    """
    Utility function that reformat the processed recipe dataset for modeling and UI purpose.

    Parameters
    ----------

    root_directory: Union[Path,str]
        Path to root directory of project

    first_chunk_only: bool
        If True, will only get 1 chunk from the dataset, for testing purpose.

    Returns
    ----------
    recipe_df: pd.DataFrame
        Formatted recipe dataset.
    """

    #NOTE: might need update to retrieve the processed df from S3

    if first_chunk_only:
        recipe_df = pd.read_csv(root_directory / "data/processed/Recipes/recipes_chunk_0.csv",usecols=RECIPE_TO_USE)
    else:
        recipe_df = load_chunks(root_directory / "data/processed/Recipes","recipes_chunk_*.csv",usecols=RECIPE_TO_USE)
    recipe_df.rename(columns = RECIPE_COLUMN_MAPPING,inplace=True)

    recipe_df['ingredients'] = recipe_df['ingredients'].fillna('[]').apply(ast.literal_eval)  # convert ingredient to list
    recipe_df['instructions'] = recipe_df['instructions'].fillna('[]').apply(ast.literal_eval)  # convert instructions to list

    if not os.path.exists(root_directory / 'data/processed/recipes_generated_features.csv'):
        recipe_category_df = pandas_sql_df("SELECT * from RECIPES")
    else:
        recipe_category_df = pd.read_csv(root_directory / "data/processed/recipes_generated_features.csv")

    recipe_category_df['original_id'] = recipe_category_df['original_id'].astype(int)
    recipe_category_df['cooking_method'] = recipe_category_df['cooking_method'].str.strip("{}").str.split(",")

    recipe_df = recipe_df.merge(recipe_category_df,on=['original_id','source'],how='inner')
    recipe_df = recipe_df.dropna(subset = RECIPE_META_COLS)
    recipe_df = recipe_df[recipe_df["ingredients"].apply(lambda x: x != [])]  # remove empty ingredient record

    #Drop recipe that take too long, or calories value that are unreasonably high for a common meal
    recipe_df = recipe_df.loc[(recipe_df['total_time']<=1440)&(recipe_df['calories']<= 5000)].reset_index(drop=True)

    return recipe_df

def load_recipe_url(
    root_directory: Union[Path,str],
    first_chunk_only: bool = False
):
    """
    Extend helper function from 'load_recipe_data' to get image_url
    """

    #NOTE: might need update to retrieve the processed df from S3

    if first_chunk_only:
        recipe_df = pd.read_csv(root_directory / "data/processed/Recipes/recipes_chunk_0.csv",usecols=RECIPE_URL_TO_USE)
    else:
        recipe_df = load_chunks(root_directory / "data/processed/Recipes","recipes_chunk_*.csv",usecols=RECIPE_URL_TO_USE)
    recipe_df.rename(columns = RECIPE_COLUMN_MAPPING,inplace=True)

    recipe_df['ingredients'] = recipe_df['ingredients'].apply(ast.literal_eval)  # convert ingredient to list

    if not os.path.exists(root_directory / 'data/processed/recipes_generated_features.csv'):
        recipe_category_df = pandas_sql_df("SELECT * from RECIPES")
    else:
        recipe_category_df = pd.read_csv(root_directory / "data/processed/recipes_generated_features.csv")

    recipe_category_df['original_id'] = recipe_category_df['original_id'].astype(int)
    recipe_category_df['cooking_method'] = recipe_category_df['cooking_method'].str.strip("{}").str.split(",")

    recipe_df = recipe_df.merge(recipe_category_df,on=['original_id','source'],how='inner')
    recipe_df = recipe_df.dropna(subset = RECIPE_META_COLS)
    recipe_df = recipe_df[recipe_df["ingredients"].apply(lambda x: x != [])]  # remove empty ingredient record

    #Drop recipe that take too long, or calories value that are unreasonably high for a common meal
    recipe_df = recipe_df.loc[(recipe_df['total_time']<=1440)&(recipe_df['calories']<= 5000)].reset_index(drop=True)

    # get only image related columns
    recipe_df = recipe_df[['recipe_id','original_id','source','image_url']]

    return recipe_df
    

def load_user_review_data(
        root_directory:Union[Path,str],
        recipe_df: pd.DataFrame,
        first_chunk_only:bool = False
    ):
    """
    Utility function that reformat the processed review dataset for modeling and UI purpose.

    Parameters
    ----------

    root_directory: Union[Path,str]
        Path to root directory of project

    first_chunk_only: bool
        If True, will only get 1 chunk from the dataset, for testing purpose.

    recipe_df: pd.DataFrame
        The recipe data prepare from 'load_recipe_data' function.

    Returns
    ----------
    user_reviews: pd.DataFrame
        Formatted review dataset.
    """
    # should sort reviews by user first

    #NOTE: might need update to retrieve the processed df from S3, remove any users that have less than n reviews
    if first_chunk_only:
        user_reviews = pd.read_csv(root_directory / "data/processed/Reviews/reviews_chunk_0.csv",usecols=REVIEW_TO_USE)
    else:
        user_reviews = load_chunks(root_directory / "data/processed/Reviews","reviews_chunk_*.csv",usecols=REVIEW_TO_USE) 
    user_reviews.rename(columns = REVIEW_COLUMN_MAPPING,inplace=True)

    # Convert datetime data
    user_reviews['modified_time'] = pd.to_datetime(user_reviews['modified_time'],format='ISO8601', utc=True)
    user_reviews['modified_time'] = user_reviews['modified_time'].dt.tz_localize(None)

    # merge with recipe_df to retrieve the unique recipe_id from Postgres database
    user_reviews = user_reviews.merge(recipe_df[['original_id','source','recipe_id']],on=['original_id','source'],how='inner')
    user_reviews = user_reviews.sort_values(['source','original_user_id']).reset_index(drop=True)

    # Convert to user from difference source to unique IDs
    user_reviews["user_id"] = user_reviews["original_user_id"].astype(str) + "_" + user_reviews["source"]

    groupby = user_reviews.groupby('user_id')['rating'].count()
    drop_index = groupby.index[groupby<10]  #NOTE: threshold for to keep user with this minimum number of reviews

    user_reviews = user_reviews.loc[~(user_reviews['user_id'].isin(drop_index))].reset_index(drop=True)
    user_reviews["user_id"], _ = pd.factorize(user_reviews["user_id"])

    user_reviews = user_reviews[['user_id','recipe_id','rating','modified_time']]

    return user_reviews

def load_preference_data(
        root_directory: Union[Path,str],
        recipe_df: pd.DataFrame,
        user_reviews: pd.DataFrame,
        batch_size: int = 5000
    ):
    """
    Utility function will load the user preference data if it exist, or creating it using the given datasets.

    Parameters
    ----------

    root_directory: Union[Path,str]
        Path to root directory of project

    recipe_df: pd.DataFrame
        The recipe data prepare from 'load_recipe_data' function.

    user_reviews: pd.DataFrame
        The review data prepare from 'load_user_review_data' function.

    batch_size: int
        The number of user to process with each batch.

    Returns
    ----------
    preference_df: pd.DataFrame
        User preference data.
    """

    if not os.path.exists(root_directory / 'data/processed/user_preferences.csv'):
        #NOTE: We can update the preference threshold if we want to
        criteria_dict = dict(
            ingredients = (0.3,'multiple'),
            cuisine = (0.25,'single'), 
            cooking_method = (0.25,'multiple'),  
            difficulty = (0.35,'single'), 
            protein_content = (0.35,'single'), 
            fiber_content = (0.35,'single'), 
            fat_content = (0.35,'single'), 
            carbohydrate_content = (0.35,'single'),
            sodium_content = (0.35,'single')
        )

        preference_df = create_user_preference(
            recipe_df,ITEM,
            user_reviews,USER,
            criteria_dict,
            RATING_COL,
            user_batch=batch_size  #NOTE: Update batch for more speed
        )
        preference_df.to_csv(root_directory / 'data/processed/user_preferences.csv',index =False)
    else:
        preference_df = pd.read_csv(root_directory / 'data/processed/user_preferences.csv')
    
    return preference_df

def construct_rec_train_dataset(
    user_reviews: pd.DataFrame,
    item_metadata: pd.DataFrame = None,
    user_preferences: pd.DataFrame = None,
    use_test_cols: bool = False,
    use_datetime: bool = False
):
    """
    Construct Rectools formatted dataset to train the recommendation models.

    Parameters
    ----------

    user_reviews: pd.DataFrame
        Contain user ratings for the items.

    item_metadata: pd.DataFrame
        Contains features of items.

    user_preferences: pd.DataFrame
        Contain user preferences for the items

    use_test_cols: bool
        If True, use the MovieLens column mapping for testing.

    use_datetime: bool
        If True, use datetime column.

    Returns
    ----------
    metrics: Dataset
        Rectools dataset object.
    """
    
    if use_test_cols:  # use MovieLens test data settings
        in_itemCol = ITEM_ML
        in_userCol = USER_ML
        in_ratingCol = RATING_ML_COL
        item_all = ML_ITEM_ALL_FEATURES
        item_cats = ML_ITEM_CAT_FEATURES
        user_cats = ML_USER_CAT_FEATURES
        explode_item_cats = EXPLODE_ML_ITEM_FEATURES
        explode_user_cats = EXPLODE_ML_USER_FEATURES
        
    else:
        in_itemCol = ITEM
        in_userCol = USER
        in_ratingCol = RATING_COL
        in_datetime = TIME_COL
        item_all = ITEM_ALL_FEATURES
        item_cats = ITEM_CAT_FEATURES
        user_cats = USER_CAT_FEATURES
        explode_item_cats = EXPLODE_ITEM_FEATURES
        explode_user_cats = EXPLODE_USER_FEATURES

    # rename features to match requirement in Rectools
    if not use_datetime:
        interactions = user_reviews.rename(columns = {
            in_userCol:"user_id",
            in_itemCol:"item_id", 
            in_ratingCol:"weight"
        })
        interactions['datetime'] = -1 # assign a random value as we won't use this
    else:
        interactions = user_reviews.rename(columns = {
            in_userCol:"user_id",
            in_itemCol:"item_id", 
            in_ratingCol:"weight",
            in_datetime:"datetime"
        })
    if user_preferences is not None:
        user_features = user_preferences.rename(columns={
            in_userCol:"user_id"
        })
        # convert category features to long format
        user_features = user_features[["user_id"] + user_cats]
        for feature in explode_user_cats:
            user_features = user_features.explode(feature)
        user_features = pd.melt(user_features, id_vars='user_id', value_vars=user_cats,var_name="feature")
        user_features.rename(columns={"user_id":"id"},inplace=True)
    else:
        user_features = None
        user_cats = ()

    if item_metadata is not None:
        item_features = item_metadata.rename(columns={
            in_itemCol:"item_id"
        })
        # convert category features to long format
        item_features = item_features[["item_id"] + item_all]
        for feature in explode_item_cats:
            item_features = item_features.explode(feature)
        item_features = pd.melt(item_features, id_vars='item_id', value_vars=item_all,var_name="feature")
        item_features.rename(columns={"item_id":"id"},inplace=True)
    else:
        item_features = None
        item_cats = ()

    # create Rectools dataset with all user/item features and iteractions
    dataset = Dataset.construct(
        interactions_df=interactions,
        user_features_df=user_features,
        cat_user_features=user_cats,
        item_features_df=item_features,
        cat_item_features=item_cats,
    )

    return dataset
