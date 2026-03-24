from tqdm.auto import tqdm

import pandas as pd
from sklearn.utils import gen_batches
from sklearn.preprocessing import MinMaxScaler,StandardScaler,OneHotEncoder,MultiLabelBinarizer

def create_user_preference(
    record_df: pd.DataFrame,
    record_id:str,
    review_df: pd.DataFrame,
    user_id:str,
    criteria_dict:dict,
    rating_col:str = 'rating',
    rating_scaler = 'min_max',
    user_batch = 10000
):
    """
    The utility function to support create user preferences from the reviews records.

    Parameters
    ----------

    record_df: pd.DataFrame
        Hold the metadata of items that the users review, should at least contain these
        columns: 'record_id' and category features of interest. 

    record_id: str
        The column which hold the unique record_id to identify the item.

    review_df: pd.DataFrame
        The dataframe that hold the users' reviews for record_df, should at least contain these
        columns: 'user_id', 'record_id' of each review, and rating column.

    criteria_dict: dict
        The filter metainfo dictionary that shall be used to create the reference. The syntax of
        each item should be 'category_col':(minimum_threshold,label_type).

        NOTE: if the category column contain list of labels then use 'multiple', if only 1 label
        then use 'single'

        Example:
            criteria_dict = dict(
                genres = (0.3,'multiple'),
                original_language = (0.1,'single')
            )

    rating_col: str
        The rating column.

    rating_scaler: str
        The type of scaler to use, either: 'min_max' or 'standard'
    
    user_batch: int
        How many user_id to process at in a batch.

    Returns
    ----------

    preference_df: pd.DataFrame
        Return the preference of each category column, if the value is [], it mean there is no
        label has crossed the threshold for that category.
    """
    reviews = review_df.sort_values(user_id).reset_index(drop=True).copy()
    user_list = reviews[user_id].unique()
    preference_df = pd.DataFrame()

    # create batch for processing to reduce memory uphead.
    batches = gen_batches(user_list.size,user_batch)  

    if rating_scaler == 'min_max':
        scaler = MinMaxScaler()
        reviews[f'normalized_{rating_col}'] = scaler.fit_transform(reviews[[rating_col]])
    else:
        scaler = StandardScaler()
        reviews[f'normalized_{rating_col}'] = scaler.fit_transform(reviews[[rating_col]])
    for batch in tqdm(list(batches), desc="Processing batches",position=0):
        keep_cols = [user_id,record_id,f'normalized_{rating_col}']

        # Retrieve only batch user_id reviews
        buffer_df = reviews.iloc[
            reviews[user_id].isin(user_list[batch])
        ][keep_cols].copy()

        merge_cols = [record_id]
        merge_cols.extend(list(criteria_dict.keys()))
        buffer_df = buffer_df.merge(record_df[merge_cols],on=record_id)  # merge records

        keep_cols = list(set(keep_cols + merge_cols))

        hold_df = pd.DataFrame()  # hold each batch preference

        for category,(threshold,cat_type) in criteria_dict.items():
            if cat_type == "single":
                encoder = OneHotEncoder(sparse_output=False)
                encoder.fit(buffer_df[[category]])

                dummy_cols = encoder.categories_[0]
                buffer_df[dummy_cols] = encoder.transform(buffer_df[[category]])
                
            else:
                encoder = MultiLabelBinarizer()
                encoder.fit(buffer_df[category])

                dummy_cols = encoder.classes_
                buffer_df[dummy_cols] = encoder.transform(buffer_df[category])
            
            # we multiply the encoded labels with normalized ratings to get its preference weight
            buffer_df[dummy_cols] = buffer_df[dummy_cols].mul(buffer_df[f'normalized_{rating_col}'],axis=0)
            # we calculate the mean of each label across all reviews of each user, we can change how we handle the average
            group_df = buffer_df.groupby(user_id)[dummy_cols].mean()  
            # only retrieve labels that cross the threshold
            pref_buffer_df = (group_df>=threshold).apply(lambda x:dummy_cols[x],axis=1).reset_index()
            pref_buffer_df.rename(columns={0:category},inplace=True)
            pref_buffer_df[category] = pref_buffer_df[category].apply(list)

            if not hold_df.empty:
                hold_df = hold_df.merge(pref_buffer_df)
            else:
                hold_df = pref_buffer_df
            buffer_df = buffer_df[keep_cols]  # reassign to reduce memory usage

        preference_df = pd.concat((preference_df,hold_df))  # append to preference df

    preference_df.reset_index(drop=True,inplace=True)
    return preference_df