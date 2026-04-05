import os
import warnings
from dotenv import load_dotenv
from typing import Union
import time
from pathlib import Path

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
        documents: Union[list,str]
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
            tokens = word_tokenize(doc.lower())
            # remove the stop words
            tokens = [tok for tok in tokens if tok not in stop_words]
            # stem the tokens
            stem_tokens = [stemmer.stem(tok) for tok in tokens]
            cleaned_docs.append(stem_tokens)
        
        return cleaned_docs
    else:
        # tokenize the text
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

class VectorstoreLoader:
    def __init__(
        self,
        collection_name,
        embedding,
        doc_template,
        input_data,
        format_cols,
        meta_cols:list=None,
        persist_directory = "./chroma_db",
        docID_col = ITEM
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
            Location to store the vector storage.

        docID_col: str
            The column that hold unique record identifier.
        """

        # Convert Pandas to Douments format
        self.raw_documents = [
            Document(
                page_content=doc_template.format(*item[format_cols]),
                metadata = {} if meta_cols is None else dict(zip(meta_cols,item[meta_cols])),
                id=item[docID_col]
            )
            for _,item in input_data.iterrows()
        ]

        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embedding,
            persist_directory=persist_directory
        )
        self.current_index = 0  # use to resume to where document loader failed


    def add_initial_documents(self,batch_size = 1000):
        """
        Document loader. Restart this method to continue from where you failed.
        """
        print(f"Starting ingestion from index {self.current_index}...")
        start = time.perf_counter()
        break_ingestion = False

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
    