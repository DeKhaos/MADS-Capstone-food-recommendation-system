"""
Utility module that can be used to support other modules.
"""
import re
import glob

import pandas as pd
import numpy as np
import dask.dataframe as dd
from sklearn import datasets
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

def require_batching(
    data_frame,
    max_mb = 100
    ):
    memory_size = data_frame.memory_usage().sum()/1024**2
    if memory_size >= max_mb:
        return True
    return False
import os

def save_dataframe(
    data_frame,
    file_name,
    directory="datasets/raw",
    max_mb=100,
    partition_size="50MB",
    chunksize=100_000
):
    os.makedirs(directory, exist_ok=True)
    path = f"{directory}/{file_name}.csv"

    df = data_frame.copy()

    for col in df.columns:
        dtype_str = str(df[col].dtype).lower()
        if "string" in dtype_str or "pyarrow" in dtype_str:
            df[col] = df[col].astype("object")

    first = True
    for start in range(0, len(df), chunksize):
        df.iloc[start:start + chunksize].to_csv(
            path,
            mode="w" if first else "a",
            header=first,
            index=False
        )
        first = False

    print("Save data completed.")
    
def save_dataframe_old(
    data_frame,
    file_name,
    directory='datasets/raw',
    max_mb = 100,
    partition_size = '50MB'
    ):
    if require_batching(data_frame,max_mb=max_mb):
        dask_df = dd.from_pandas(data_frame,npartitions=1)
        dask_df = dask_df.repartition(partition_size=partition_size)
        dask_df.to_csv(directory + '/' + file_name + '*.csv',index=False)
    else:
        data_frame.to_csv(directory + '/' + file_name + '.csv',index=False)
    print('Save data completed.')
    
def read_data(
    file_name: str,
    directory: str ='datasets/raw',
    convert_pandas: bool = True
):
    path = directory + '/' + file_name + '*.csv'
    files = glob.glob(path)

    n = len(files)
    if n > 1:  # a dask directory with multiple csv
        dask_df = dd.read_csv(path)
        # convert to pandas df
        if convert_pandas:
            pd_df = dask_df.compute().reset_index(drop=True)
            return pd_df
        else:
            return dask_df
    elif n == 1:  # a csv file
        pd_df = pd.read_csv(files[0])
        return pd_df
    else:
        raise Exception('No file found.')

def get_target_labels(
    dataset = 'iris',
    binary_label = True
    ):
    
    if dataset == 'iris':
        labels = datasets.load_iris()['target_names']
    elif dataset == 'cancer':
        labels = datasets.load_breast_cancer()['target_names']
    else:
        labels = []
    if binary_label:
        labels = list(labels[:1]) + ['other']
    return list(labels)

def get_feature_labels(
    dataset = 'iris'
    ):
    
    if dataset == 'iris':
        labels = datasets.load_iris()['feature_names']
    elif dataset == 'cancer':
        labels = datasets.load_breast_cancer()['feature_names']
    elif dataset == 'diabetes':
        labels = datasets.load_diabetes()['feature_names']
    else:
        labels = []
    return labels

def generate_data(
    dataset = 'iris',
    test_size=0.2,
    binary_label = True,
    add_random = False,
    seed=None
    ):

    if dataset == 'iris':
        X, y = datasets.load_iris(return_X_y=True)
    elif dataset == 'cancer':
        X, y = datasets.load_breast_cancer(return_X_y=True)
    elif dataset == 'diabetes':
        X, y = datasets.load_diabetes(return_X_y=True)
    else:
        data = None

    np.random.seed(seed)
    if add_random:
        n_samples, n_features = X.shape
        X = np.concatenate([X, np.random.randn(n_samples, 200 * n_features)], axis=1)

    # X = data.data
    # y = data.target
    if np.unique(y).size > 10: # assume continuous data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=test_size,
            random_state=seed
        )
        return X_train, X_test, y_train, y_test
    else:
        if binary_label:
            X_train, X_test, y_train, y_test = train_test_split(
                X[y<2], y[y<2], 
                test_size=test_size,
                stratify = y[y<2],
                random_state=seed
            )
        else:
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, 
                test_size=test_size,
                stratify = y,
                random_state=seed
                )
        return X_train, X_test, y_train, y_test
