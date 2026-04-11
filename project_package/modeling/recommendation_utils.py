import os
import warnings
from dotenv import load_dotenv
from typing import Union,List,Tuple,Literal
import time
from pathlib import Path
import string

import nltk
from nltk import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import SnowballStemmer
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import paired_cosine_distances
from rectools import ExternalIds
from rectools.metrics.distances import PairwiseDistanceCalculator
from rectools.metrics import (
    Recall,
    Precision,
    NDCG,
    AvgRecPopularity,
    IntraListDiversity,
    Serendipity,
    MeanInvUserFreq
)
from rectools.dataset import Dataset
from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_compressors import FlashrankRerank
import chromadb
from chromadb.config import Settings
from rank_bm25 import BM25Plus
from flashrank import Ranker
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from project_package.data_preprocessing.default import (
    USER,ITEM,RATING_COL,
    ITEM_CAT_FEATURES,USER_CAT_FEATURES,EXPLODE_ITEM_FEATURES,EXPLODE_USER_FEATURES,
    USER_ML,ITEM_ML,RATING_ML_COL,
    ML_ITEM_CAT_FEATURES,ML_USER_CAT_FEATURES,EXPLODE_ML_ITEM_FEATURES,EXPLODE_ML_USER_FEATURES
)

load_dotenv()  # load variable from .env file

if os.environ["NTLK_DATA_PATH"] not in nltk.data.path:
    nltk.data.path.append(os.environ["NTLK_DATA_PATH"])

try:
    nltk.data.find('/tokenizers/punkt_tab')  # check of module is already downloaded?
except:
    nltk.download('punkt_tab', download_dir=os.environ["NTLK_DATA_PATH"])

class PairwiseCosineDistanceCalculator(PairwiseDistanceCalculator):
    """
    Class for computing Cosine distance between pairs of items using dense embeddings.
    
    Parameters
    ----------
    item_embeddings_df: pandas.DataFrame
        Dataframe where the index consists of item IDs and the columns are 
        the embedding dimensions (e.g., from ChromaDB).
    """

    def __init__(self, item_embeddings_df: pd.DataFrame) -> None:
        # We store a copy to avoid side effects
        self.embeddings_df = item_embeddings_df.copy()

    def _get_distances_for_item_pairs(self, items_0: ExternalIds, items_1: ExternalIds) -> np.ndarray:
        # 1. Reindex to get the vectors for the specific pairs requested
        # Using .reindex ensures we handle missing IDs gracefully (they become NaNs)
        features_0 = self.embeddings_df.reindex(items_0).values
        features_1 = self.embeddings_df.reindex(items_1).values

        # 2. Create masks for items that don't have embeddings (NaNs)
        mask_0 = np.isnan(features_0).any(axis=1)
        mask_1 = np.isnan(features_1).any(axis=1)
        invalid_mask = mask_0 | mask_1

        if invalid_mask.any():
            warnings.warn(
                "Some items missing embeddings. Corresponding pair distances set to NaN."
            )

        # 3. Calculate paired cosine distances
        # We fill NaNs with 0 temporarily for the sklearn function, then mask them back
        feat_0_clean = np.nan_to_num(features_0)
        feat_1_clean = np.nan_to_num(features_1)
        
        # paired_cosine_distances returns 1 - cosine_similarity
        result = paired_cosine_distances(feat_0_clean, feat_1_clean).astype(np.float64)

        # 4. Apply the NaN mask to items that weren't found in the embedding dataframe
        result[invalid_mask] = np.nan
        
        return result
    
def preprocessing_docs(
        documents: Union[list,str],
        remove_punctuation: bool = False
    ):
    """
    Preprocessing text function.

    Parameters
    ----------

    documents: Union[list,str]
        Take either a list of documents of a single document to process.

    Returns
    ----------
    Union[list,str]
        THe cleaned document(s).
    """
    stop_words = set(stopwords.words("english"))
    stemmer = SnowballStemmer("english")

    if isinstance(documents,list):
        cleaned_docs = []
        for doc in documents:
            # tokenize the text
            if remove_punctuation: # remove punctuation
                tokens = word_tokenize(
                    doc.translate(str.maketrans('', '', string.punctuation)).lower()
                )
            else:
                tokens = word_tokenize(doc.lower())
            # remove the stop words
            tokens = [tok for tok in tokens if tok not in stop_words]
            # stem the tokens
            stem_tokens = [stemmer.stem(tok) for tok in tokens]
            cleaned_docs.append(stem_tokens)
        
        return cleaned_docs
    else:
        # tokenize the text
        if remove_punctuation: # remove punctuation
            tokens = word_tokenize(
                documents.translate(str.maketrans('', '', string.punctuation)).lower()
            )
        else:
            tokens = word_tokenize(documents.lower())
        # remove the stop words
        tokens = [tok for tok in tokens if tok not in stop_words]
        # stem the tokens
        stem_tokens = [stemmer.stem(tok) for tok in tokens]
        return stem_tokens

def generate_metric_objs(
    embedding_docs: pd.DataFrame,
    k:int = 10
):
    """
    Generate evaluation metric objects for recommendation system.

    Parameters
    ----------

    embedding_docs: pd.DataFrame
        Retrieve the item embedding vectors from Chroma vectorstore.

    Returns
    ----------
    metrics: dict
        Dictionary of metric objects.
    """
    distance_calculator = PairwiseCosineDistanceCalculator(embedding_docs)  # use cosine distance calculator
    ild = IntraListDiversity(k=k, distance_calculator=distance_calculator)

    metrics = {
        f"Recall@{k}":Recall(k=k),
        f"Precision@{k}":Precision(k=k, r_precision=True),
        f"NDCG@{k}":NDCG(k=k),
        f"AvgRecPopularity@{k}":AvgRecPopularity(k=k,normalize=True),
        f'Serendipity@{k}': Serendipity(k=k),
        f"Diversity@{k}":ild,
        f"Novelty@{k}":MeanInvUserFreq(k=k),
    }

    return metrics

def construct_rec_train_dataset(
    user_reviews: pd.DataFrame,
    item_metadata: pd.DataFrame = None,
    user_preferences: pd.DataFrame = None,
    use_test_cols: bool = False
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

    Returns
    ----------
    metrics: Dataset
        Rectools dataset object.
    """
    
    if use_test_cols:  # use MovieLens test data settings
        in_itemCol = ITEM_ML
        in_userCol = USER_ML
        in_ratingCol = RATING_ML_COL
        item_cats = ML_ITEM_CAT_FEATURES
        user_cats = ML_USER_CAT_FEATURES
        explode_item_cats = EXPLODE_ML_ITEM_FEATURES
        explode_user_cats = EXPLODE_ML_USER_FEATURES
        
    else:
        in_itemCol = ITEM
        in_userCol = USER
        in_ratingCol = RATING_COL
        item_cats = ITEM_CAT_FEATURES
        user_cats = USER_CAT_FEATURES
        explode_item_cats = EXPLODE_ITEM_FEATURES
        explode_user_cats = EXPLODE_USER_FEATURES

    # rename features to match requirement in Rectools
    interactions = user_reviews.rename(columns = {
        in_userCol:"user_id",
        in_itemCol:"item_id", 
        in_ratingCol:"weight"
    })
    interactions['datetime'] = -1 # assign a random value as we won't use this

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
        item_features = item_features[["item_id"] + item_cats]
        for feature in explode_item_cats:
            item_features = item_features.explode(feature)
        item_features = pd.melt(item_features, id_vars='item_id', value_vars=item_cats,var_name="feature")
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

def doc_template_fill_in(
    doc_template: str,
    input_data: pd.DataFrame,
    format_cols: list,
    meta_cols: list = None,
    docID_col: str = ITEM
):
    """
    Fill in a document template using Pandas dataframe records, each row will be its own document.

    Parameters
    ----------

    doc_template: str
        Document template with placeholders

    input_data: pd.DataFrame
        DataFrame that need to be processed.

    format_cols: list
        List of columns to fill in template placeholders for each document.
    
    meta_cols: list
        List of columns to be used for document metadata.

    docID_col: str
        The column that hold unique record identifier.

    Returns
    ----------
    documents: List[Document]
        List of documents with metadata
    """

    documents = [
        Document(
            page_content=doc_template.format(*item[format_cols]),
            metadata = {} if meta_cols is None else dict(zip(meta_cols,item[meta_cols])),
            id=item[docID_col]
        )
        for _,item in input_data.iterrows()
    ]

    return documents

def load_vector_store(
    collection_name: str,
    embedding_model: HuggingFaceEmbeddings,
    persist_directory="./chroma_db"
):
    """
    Utility function to load the Chroma vectorstore, priority trying to get the cloud service. If
    not possible, switch to use local storage instead.

    Parameters
    ----------

    collection_name: str
            The collection name

    embedding_model: HuggingFaceEmbeddings
        The embedding model to transform the document

    persist_directory: str
        Local machine directory to store the vector storage if the cloud fails.

    Returns
    ----------
    vectorstore: Chroma
    """
    try:
        chroma_client = chromadb.HttpClient(
            host=os.environ["CHROMA_HOST_IP"],
            port=8000,
            settings = Settings(
                chroma_client_auth_provider="chromadb.auth.token_authn.TokenAuthClientProvider",
                chroma_client_auth_credentials=os.environ["CHROMA_ACCESS_KEY"],
                chroma_auth_token_transport_header="Authorization"
            )
        )
        vectorstore = Chroma(
            client=chroma_client,
            collection_name=collection_name,
            embedding_function=embedding_model,
        )
    except:
        print("Couldn't load the cloud Chroma vectorstore, switching to local storage.")
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embedding_model,
            persist_directory=persist_directory
        )
    return vectorstore

class VectorstoreLoader:
    def __init__(
        self,
        collection_name: str,
        embedding: HuggingFaceEmbeddings,
        doc_template: str,
        input_data: pd.DataFrame,
        format_cols: list,
        meta_cols: list = None,
        persist_directory: str = "./chroma_db",
        docID_col: str = ITEM
        ):
        """
        Vectorstore loading class which help create documents from DataFrame and load it to vector store

        Parameters
        ----------

        collection_name: str
            The collection name

        embedding: HuggingFaceEmbeddings
            The embedding model to transform the document

        doc_template: str
            Document template with placeholders

        input_data: pd.DataFrame
            DataFrame that need to be processed.

        format_cols: list
            List of columns to fill in template placeholders for each document.
        
        meta_cols: list
            List of columns to be used for document metadata.

        persist_directory: str
            Local machine directory to store the vector storage if the cloud fails.

        docID_col: str
            The column that hold unique record identifier.
        """

        # Convert Pandas to Douments format
        self.raw_documents = doc_template_fill_in(doc_template,input_data,format_cols,meta_cols,docID_col)

        self.vectorstore = load_vector_store(collection_name,embedding,persist_directory)
        self.current_index = 0  # use to resume to where document loader failed


    def add_initial_documents(self,batch_size:int = 1000,start_index:int=None):
        """
        Document loader. Restart this method to continue from where you failed.
        """
        print(f"Starting ingestion from index {self.current_index}...")
        start = time.perf_counter()
        break_ingestion = False
        if start_index is not None:  # start from a user defined index instead
            self.current_index = start_index
        for i in tqdm(range(self.current_index, len(self.raw_documents), batch_size)):
            batch = self.raw_documents[i : i + batch_size]
            
            try:
                # We manually track the "current" successful index
                self.vectorstore.add_documents(batch)
            except Exception as e:
                print(e)
                print(f"[ERROR] Failed at index: {i}")
                print(f"To resume, run this instance method again or debug the documents.")
                self.current_index = i
                break_ingestion = True
                break
        end = time.perf_counter()
        calculated_time = round(end - start,2)
        if break_ingestion:
            print(f'Calculation time for embeddings before error: {calculated_time}s')
            return False
        else:
            print(f'Calculation time for embeddings: {calculated_time}s')
            print("Data ingestion completed.")
            return True

    def return_vectorstore(self):
        """
        Return Chroma vector store object.
        """
        return self.vectorstore

def get_embedding_model(
    huggingface_model_path: str,
    local_model_name: str,
    device:str = "cpu"
):
    """
    Save a hugging embedding model to local storage.

    Parameters
    ----------

    huggingface_model_path: str
        Path to the directory of the model in HuggingFace

    local_model_name: str
        Local directory to store the model.

    device: str
        Choose between 'cpu' or 'cuda'.

    Returns
    ----------
    embedding_model
    """
    if os.environ["EMBEDDING_PATH"] == '' or os.environ["EMBEDDING_PATH"] is None:
        raise ValueError("Local storage path for embedding models hasn't been set in .env")
    storage_dir = Path(os.environ["EMBEDDING_PATH"])

    if not os.path.exists(storage_dir / local_model_name):
        model = SentenceTransformer(huggingface_model_path) 
        model.save(storage_dir / local_model_name)

    embedding_model = HuggingFaceEmbeddings(
        model_name= str(storage_dir / local_model_name),
        model_kwargs={"device": device}
    )

    return embedding_model

def keep_n_labels(
    df: pd.DataFrame,
    feature: str,
    require_explode: bool = False,
    labels: Union[List[str],int] = 10
):
    """
    Utilize function set up dataframe for recommendation result analysis. Keep only n top repeated labels.

    Parameters
    ----------

    df: pd.DataFrame
        Path to the directory of the model in HuggingFace

    feature: str
        The column to process.

    require_explode: bool
        Set to True to convert the feature to long format if the values of feature are list.

    labels:Union[List[str],int]
        If number, keep the top 'labels'. If a list, will try to retain those labels after filtering.

    Returns
    ----------
    process_data: pd.DataFrame
    """

    process_data = df.copy()

    if  require_explode:
        process_data = process_data.explode(feature)

    if isinstance(labels,int):
        retrieve_labels = process_data[feature].value_counts().index[:labels]
    else:
        retrieve_labels = labels
        
    process_data = process_data.loc[process_data[feature].isin(retrieve_labels)].reset_index(drop = True)

    return process_data

def get_random_weighted_items(
    df: pd.DataFrame,
    weight_feature:str,
    size = 10,
    replace: bool = False,
    random_state: int = None
):
    """
    Get n random weight labels of a category feature from an input dataframe.

    Parameters
    ----------

    df: pd.DataFrame
        Path to the directory of the model in HuggingFace

    weight_feature: str
        The column to process.

    size: int
        Number of item to retrieve.

    replace: bool
        Should it the label can be chosen repeatibly or not.

    random_state: int
        Random seed for preproducibility.

    Returns
    ----------
    process_data: pd.DataFrame
    """
    np.random.seed(random_state)  # can turn seed on/off

    counts = df[weight_feature].value_counts()

    # Exact IDs and the weights
    items = counts.index.values
    weights = counts.values

    # Normalize the weights
    probabilities = weights / weights.sum()

    chosen_items = np.random.choice(
        items, 
        size=size, 
        replace=replace, 
        p=probabilities
    )

    return chosen_items

def apply_bias_boost(
        doc: str,
        initial_score: float,
        pos_bias:str='',
        neg_bias:str='', 
        weight: float = 0.35
    ):
    """
    Apply bias to the document ranking step by introduction weighted pull bias.

    Parameters
    ----------

    doc: str
        The document to compare.

    initial_score: float
        Initial rank score of the document.

    pos_bias: str
        Positive bias string.

    neg_bias: str
        Negative bias string.

    weight: float
        The weight of the added bias, should be in [0,1] but can go >= 1 for more strength.

    Returns
    ----------
    score: float
        The adjusted document score.
    """
    
    # Calculate intersections
    doc_set = set(preprocessing_docs(doc,True))
    pos_bias_set = set(preprocessing_docs(pos_bias,True))
    neg_bias_set = set(preprocessing_docs(neg_bias,True))

    # Find words that are in BOTH bias lists
    conflicting_tokens = pos_bias_set.intersection(neg_bias_set)
    pos_bias_set = pos_bias_set - conflicting_tokens
    neg_bias_set = neg_bias_set - conflicting_tokens

    def get_overlap(d_set, b_set):
        """
        Calculate raw overlap ratios
        """
        if b_set == set(): 
            return 0
        intersection = d_set.intersection(b_set)

        return len(intersection) / len(b_set)
    
    
    raw_pos = get_overlap(doc_set, pos_bias_set)
    raw_neg = get_overlap(doc_set, neg_bias_set)

    #Mutual Inhibition - Penalize the pull based on the opposite strength
    adj_pos = raw_pos * (1 - raw_neg)
    adj_neg = raw_neg * (1 - raw_pos)

    net_bias = adj_pos - adj_neg

    if net_bias > 0:
        # Boost: Pull from current score up toward 1.0
        gap = 1.0 - initial_score
        final_score = initial_score + (net_bias * weight * gap)
    elif net_bias < 0:
        # Unboost: Pull from current score down toward 0.0
        gap = initial_score
        final_score = initial_score + (net_bias * weight * gap)
    else:
        return initial_score

    return np.clip(final_score, 0.0, 1.0)

def recommendation_doc_id_pipeline(
    data_df: pd.DataFrame,
    vectorstore: Chroma,
    rank_model: Ranker,
    query: str,
    dataset: Dataset = None,
    user_profile: str = None,
    user_vectorstore: Chroma = None,
    recommendation_model: object = None,
    embedding_model: HuggingFaceEmbeddings = None,
    model_type: Literal['item-content','collab','hybrid'] = 'item-content',
    add_biases: List[Tuple] = None,
    remove_biases: List[Tuple] = None,
    features: List[str] = None,
    candidate: int = 1000,
    n_recommendations: int = 100,
    n_user: int = 10,
    n_rank: int = 10,
    include_fulldata: bool = False,
    pos_rank_bias: str = None,
    neg_rank_bias: str = None,
    ranker_bias_weight: float = 0.35,
    weighted_rank_config: dict = None,
    toy_dataset: bool = False,
    random_state: int = None
):
    """
    Pipeline to retrieve and store document ID for each pipeline step 
    from various recommendation models.

    Parameters
    ----------

    data_df: pd.DataFrame
        The full input dataset.

    vectorstore: Chroma
        The vector store object to query.

    rank_model: Ranker
        The reranker model use to rank the recommendations.

    query: str
        The query to search for recommendation.

    dataset: Dataset
        The Rectools format dataset to use as model input.
    
    user_profile: str
        The user query use to search for other similar users.

    user_vectorstore: Chroma
        The vector store user profile object to query.

    recommendation_model: Rectools model object
        The trained model use for prediction
    
    embedding_model: HuggingFaceEmbeddings
        The embedding model to use from HuggingFace.

    model_type: Literal['item-content','collab','hybrid']
        Choose the correct model type to run the correct step, accomodate by 'recommendation_model'.

    add_biases: List[Tuple]
        The list of biases to add to the query as vector, each item should be (bias_query,weight).

    remove_biases: List[Tuple]
        The list of biases to remove from the query as vector, each item should be (bias_query,weight).

    features: List[str]
        List of column to include in the output dataframe.

    candidate: int
        Number of candidates to retrieve after querying the chroma vectorstore

    n_recommendations: int
        Number of top recommendation to retrieve from the recommendation model
    
    n_user: int
        Number of similar users to retrieve.

    n_rank: int
        Numer of top reranked item to retrieve.

    include_fulldata: bool
        If True, include the input dataframe information in the output.

    pos_rank_bias: str
        The bias string to increase the scores of ranker documents.
    
    neg_rank_bias: str
        The bias string to decrease the scores of ranker documents.

    ranker_bias_weight: float
        The pull weight of the bias used for recalibrate ranker scores.

    weighted_rank_config: dict
        If you want to weight the ranking based on some other feature beside Ranking score, we can use it using this format.
        {
            "ranker_weight": a_value,
            "feature_weight": b_value,
            "feature_name": name,
            "feature_min": min_value,
            "feature_max": max_value
        }
    
    toy_dataset: bool
        If True, using the toy dataset default key values.

    random_state: int
        Random seed for preproducibility.
            
    Returns
    ----------
    doc_id_df: pd.DataFrame
        The retrieved document IDs from the pipeline, each step is classified using column name 'pipeline_step'

    score_df: pd.DataFrame
        The ranking score of the final recommendation items to show the users.
    """

    # Checking pipeline condition upfront
    if model_type == 'item-content':
        if embedding_model is None:
            raise ValueError("Missing 'embedding_model'.")
    elif model_type == 'collab':
        if dataset is None:
            raise ValueError("Missing 'dataset'.")
        if user_vectorstore is None:
            raise ValueError("Missing 'user_vectorstore'.")
        if recommendation_model is None:
            raise ValueError("Missing 'recommendation_model'.")
        if user_profile is None:
            raise ValueError("Missing 'user_profile'.")
    else: # hybrid
        if embedding_model is None:
            raise ValueError("Missing 'embedding_model'.")
        if dataset is None:
            raise ValueError("Missing 'dataset'.")
        if user_vectorstore is None:
            raise ValueError("Missing 'user_vectorstore'.")
        if recommendation_model is None:
            raise ValueError("Missing 'recommendation_model'.")
        if user_profile is None:
            raise ValueError("Missing 'user_profile'.")

    if toy_dataset:
        item_id = ITEM_ML
    else:
        item_id = ITEM

    if include_fulldata:
        pre_filt_df = data_df[[item_id] if features is None else [item_id] + features].copy()
        pre_filt_df['pipeline_step'] = 'full_data'
    
    # Layer 1: candidate
    if model_type  in ['item-content','hybrid']:
        query_array = np.array(embedding_model.embed_query(query))

        if add_biases is not None:
            for (bias_query,weight) in add_biases:
                bias_array = np.array(embedding_model.embed_query(bias_query))
                query_array += weight*bias_array  # add bias weight to query

        if remove_biases is not None:
            for (bias_query,weight) in remove_biases:
                bias_array = np.array(embedding_model.embed_query(bias_query))
                query_array -= weight*bias_array  # remove bias weight to query

        
        retrieved_items = vectorstore.similarity_search_by_vector(query_array,k=candidate)
        candidate_ids = np.array([item.id for item in retrieved_items],dtype=int)
        result_docs = [item.page_content for item in retrieved_items]

        candidate_df = data_df.loc[
            data_df[item_id].isin(candidate_ids),
            [item_id] if features is None else [item_id] + features
        ].copy()

        candidate_df['pipeline_step'] = 'candidate'

    # Layer 2: recommendation
    if model_type =='item-content':
        tokenized_corpus = preprocessing_docs(result_docs)
        tokenized_query = preprocessing_docs(query)
        
        bm25 = BM25Plus(tokenized_corpus)

        doc_scores = bm25.get_scores(tokenized_query)

        top_n = candidate_ids[np.argsort(doc_scores)[::-1][:n_recommendations]]  # sort the similarity score descendingly
        top_n_docs = vectorstore.get_by_ids(top_n.astype(str))

    elif model_type == 'collab':
        # Creating recommendation, collaboration is trained on entire dataset and it can only see items used in trained model
        retrieved_users = user_vectorstore.similarity_search(user_profile,k=n_user)
        match_user_ids = np.array([item.id for item in retrieved_users],dtype=int)
        
        model_recommendations = recommendation_model.recommend(
            users=match_user_ids,
            dataset=dataset,
            k=n_recommendations,
            filter_viewed=False
        )

        # we generate random choice of recommendation from the items from the similar users
        top_n = get_random_weighted_items(
            model_recommendations,"item_id",
            size=n_recommendations,random_state=random_state
        )

        top_n_docs = vectorstore.get_by_ids(top_n.astype(str)) 
        # top_n_docs might return less documents than top_n due to document in review but 
        # not in metadata,so we need to recalculate 
        top_n = np.array([item.id for item in top_n_docs],dtype=int)

    else: # hybrid
        # Creating recommendation, collaboration is trained on entire dataset and it can only see items used in trained model
        retrieved_users = user_vectorstore.similarity_search(user_profile,k=n_user)
        match_user_ids = np.array([item.id for item in retrieved_users],dtype=int)

        model_recommendations = recommendation_model.recommend(
            users=match_user_ids,  # we also reuse similar users as we don't have rating for new user yet
            dataset=dataset,
            k=n_recommendations,
            items_to_recommend=candidate_ids, # Can contain either hot or warm items
            filter_viewed = False
        )

        # them we sum the score group by each recommended items and sort them
        top_n = model_recommendations.groupby('item_id')['score'].sum().sort_values(ascending=False).index[:n_recommendations].to_numpy()
        top_n_docs = vectorstore.get_by_ids(top_n.astype(str))

    rec_df = data_df.loc[
        data_df[item_id].isin(top_n),
        [item_id] if features is None else [item_id] + features
    ].copy()
    rec_df['pipeline_step'] = 'recommendation'

    # Layer 3: Top n ranked
    doc_ids_map = dict(
        zip(range(len(top_n)),top_n.tolist())
    )
    compressor = FlashrankRerank(client=rank_model,top_n=n_rank)

    rerank_result = compressor.compress_documents(
        top_n_docs,
        query = query
    )
    
    for doc in rerank_result:  # reranking override the doc id so need to change it bank
        doc.metadata['id'] = doc_ids_map[doc.metadata['id']]

    rank_data = []
    for doc in rerank_result:   # your list of Document objects
        row = doc.metadata.copy()
        row["page_content"] = doc.page_content
        rank_data.append(row)

    score_df = pd.DataFrame(rank_data)[['id','relevance_score','page_content']]
    score_df.rename(columns={"id":item_id},inplace=True)

    if pos_rank_bias or neg_rank_bias:  # Recalibrate the ranking score base on bias strings
        pos_rank_bias = "" if pos_rank_bias is None else pos_rank_bias
        neg_rank_bias = "" if neg_rank_bias is None else neg_rank_bias
        score_df['relevance_score'] = score_df.apply(
            lambda x:apply_bias_boost(
                x['page_content'], x['relevance_score'],
                pos_bias=pos_rank_bias,
                neg_bias=neg_rank_bias,
                weight=ranker_bias_weight),
                axis=1
        )
        score_df = score_df.sort_values('relevance_score',ascending=False).reset_index(drop=True)

    if weighted_rank_config is not None:  # reweight the score based on new feature
        ranker_weight = weighted_rank_config["ranker_weight"]
        f_weight = weighted_rank_config["feature_weight"]
        f_name = weighted_rank_config["feature_name"]
        f_min = weighted_rank_config["feature_min"]
        f_max = weighted_rank_config["feature_max"]

        score_df = score_df.merge(data_df[[item_id,f_name]],on=item_id,how='left')

        score_df[f_name] = (score_df[f_name] - f_min)/(f_max-f_min)  # normalize the feature to [0,1]
        score_df['relevance_score'] = ranker_weight*score_df['relevance_score'] + f_weight*score_df[f_name]  # recaculate the ranker score
        score_df = score_df[[item_id,'relevance_score','page_content']]
        score_df = score_df.sort_values('relevance_score',ascending=False).reset_index(drop=True)

    ranked_ids = np.array([doc.metadata['id'] for doc in rerank_result])
    rank_df = data_df.loc[
        data_df[item_id].isin(ranked_ids),
        [item_id] if features is None else [item_id] + features
    ].copy()
    rank_df['pipeline_step'] = 'ranked'

    if include_fulldata:
        if model_type == 'item-content':
            doc_id_df = pd.concat((pre_filt_df,candidate_df,rec_df,rank_df)).reset_index(drop=True)
        else:
            doc_id_df = pd.concat((pre_filt_df,rec_df,rank_df)).reset_index(drop=True)
    else:
        if model_type == 'item-content':
            doc_id_df = pd.concat((candidate_df,rec_df,rank_df)).reset_index(drop=True)
        else:
            doc_id_df = pd.concat((rec_df,rank_df)).reset_index(drop=True)

    return doc_id_df,score_df