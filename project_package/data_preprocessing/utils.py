from tqdm.auto import tqdm
from typing import Union

import pandas as pd
import numpy as np
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
        buffer_df = reviews.loc[
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
                dummy_cols = np.array([str(c) for c in encoder.categories_[0]])  # To convert any False,True to string
                encoded = pd.DataFrame(
                    encoder.transform(buffer_df[[category]]),
                    columns=dummy_cols,
                    index=buffer_df.index
                )

                
            else:
                encoder = MultiLabelBinarizer()
                encoder.fit(buffer_df[category])
                dummy_cols = np.array([str(c) for c in encoder.classes_])  # To convert any False,True to string
                encoded = pd.DataFrame(
                    encoder.transform(buffer_df[category]),
                    columns=dummy_cols,
                    index=buffer_df.index
                )
            buffer_df = pd.concat([buffer_df, encoded], axis=1)

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

def chroma_filter_operator(
    filter_data: Union[dict,pd.DataFrame],
    operator_type_mapping: Union[dict,pd.DataFrame],
    filter_name_mapping: dict = None
):
    """
    Support creating metadata filtering syntax that can be feed into the Chroma vectorstore as retriever.

    Parameters
    ----------

    filter_data: dict | pd.DataFrame
        Filter information retrieved from UI filters, which is store in the dcc.Store(id=<filter_store_id>).
        The filter values will always be either a list of label, or a 2-items list used in range slider.

    operator_type_mapping: dict | pd.DataFrame
        Mapping which Chroma vectorstore logic operations to use for each filter. The input template should be
        like this dict(
            filter_name = [<filter_name1>,<filter_name2>,...],
            operator_type = [<chain_operator1>,<chain_operator2>,...]
        )

        Example for chain operator:
        
            If the record value is string, use $in or $nin. 
            If the record value is number then use $in or $nin, $range should be used if the filter is a range slider.
            If the record value is a list of labels, use chain operator with iether $or or $and follow by ':' then
            $contains or $not_contains. E.g $or:$contains
            NOTE: $range is a custom syntax for this function. For more Chroma vectorstore syntax, please refer to
            https://docs.trychroma.com/docs/querying-collections/metadata-filtering#using-inclusion-operators

        filter_name_mapping: dict
            Map the filter names to the vectorstore column names if their names are different.
        
    Returns
    ----------

    filter_operators: dict
        Return a dictionary of nested chain operator for each filter.
    """

    if not isinstance(filter_data,pd.DataFrame):
        filter_data = pd.DataFrame(filter_data)
    
    if not isinstance(operator_type_mapping,pd.DataFrame):
        operator_type_df = pd.DataFrame(operator_type_mapping)
    else:
        operator_type_df = operator_type_mapping
        
    applicable_filters = filter_data.loc[filter_data['priority_type']=="exact"].copy()  # create operators only for exact filters
    if applicable_filters.shape[0] == 0:
        return {}
    
    operator_type_df = pd.DataFrame(operator_type_mapping)

    if filter_name_mapping is not None:
        applicable_filters['filter_name'] = applicable_filters['filter_name'].apply(lambda x:filter_name_mapping.get(x,x))
        operator_type_df['filter_name'] = operator_type_df['filter_name'].apply(lambda x:filter_name_mapping.get(x,x))
        
    applicable_filters = applicable_filters.merge(operator_type_df,on='filter_name')

    filter_operators = []

    for _,info in applicable_filters.iterrows():
        if info["filter_value"] in (None,[]):  # skip filters that don't have a value
            continue
        elif info["operator_type"] == "$range":  # range slider
            add_operators = {
                "$and":[
                    {info["filter_name"]: {"$gte": info["filter_value"][0]}},
                    {info["filter_name"]: {"$lte": info["filter_value"][1]}},
                ]
            }
        elif ':' in info["operator_type"]:  # handle logic for comparing a list of filter items with the record item list.
            if 'ingredients' not in info["filter_name"]:  # check for like/dislike ingredients
                filter_name = info["filter_name"]
            else:  # if we have ingredient1,ingredient2 (like,dislike ingredients)
                filter_name = 'ingredients'

            and_or_operator,contain_operator = info["operator_type"].split(":")
            if len(info["filter_value"])>1:
                add_operators = {
                    and_or_operator:[
                        {filter_name:{contain_operator:item}} for item in info["filter_value"]
                    ]
                }
            else:  # if only 1 item in list, drop the 'and_or_operator
                add_operators = {
                    filter_name:{contain_operator:info["filter_value"][0]}
                }

        else: # "$in|$nin"
            add_operators = {
                info["filter_name"]:{info["operator_type"]:info["filter_value"]}
            }
        filter_operators.append(add_operators)
    
    if len(filter_operators) == 1:
        filter_operators = filter_operators[0]
    else:
        filter_operators = {"$and":filter_operators}  # each distinct filter operators must match
    
    return filter_operators