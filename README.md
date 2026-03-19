# Food recipe recommendation system

MADS Capstone Project: A food recipe recommendation system to help users find a matching recipe, its nutrient, cooking steps, etc.


## Installation

This project runs stable on Python version 3.11.

From the main directory, the users can install the package requirement using the PIP command:

```
pip install -r requirements.txt
```

or you can also use the customized Makefile command, which include creating .env variables from template:

```
make setup
```

## Start the application

To run the web UI locally, you can run the following command, it will host the application in a local port.

```
python -m dash_app.app
```

## Project Organization

```
├── LICENSE            <- Open-source license.
├── Makefile           <- Makefile with convenience commands.
├── README.md          <- The top-level README.
├── dash_app
│   ├── pages          <- Web UI pages.
│   └── assets         <- Web UI assets such as css, png files,etc.
│
├── data
│   ├── external       <- Data from third party sources, if necessary.
│   ├── interim        <- Intermediate data that has been transformed, if necessary stored.
│   ├── processed      <- The final, canonical data sets for modeling.
│   └── raw            <- Used to store original datasets, can have subfolder to store different datasets.
│
├── docs               <- To store any documents, if necessary.
│
├── models             <- Trained and serialized models, model predictions, or model summaries
│
├── notebooks          <- Jupyter notebooks. Naming convention is a number (for ordering), 
│                         e.g. `1.1. Review_data_collection.ipynb`, `1.2. Recipe_data_collection.ipynb`.
│
├── pyproject.toml     <- Project configuration file with package metadata for 
│                         project_package and configuration for tools like black
│
├── references         <- Data dictionaries, manuals, and all other explanatory materials.
│
├── reports            <- Generated analysis as HTML, PDF, LaTeX, etc.
│   └── figures        <- Generated graphics and figures to be used in reporting, if any.
│
├── requirements.txt   <- The requirements file for reproducing the analysis environment, e.g.
│                         generated with `pip freeze > requirements.txt`
│
├── setup.cfg          <- Configuration file for flake8
│
└── project_package   <- Source code for use in this project.
    │
    ├── __init__.py             <- Makes project_package a Python module
    │
    ├── config.py               <- Store useful variables and configuration
    │
    ├── **.py                   <- Code arrange by purposes.
    │
    └── subpackages             <- Folder that store subpackages like data collection, preprocess, etc.
```

## Contributors
* Kha Nguyen (minhkha@umich.edu)
* Naiwen Duan (nduan@umich.edu)
* Susan Oseili (usanhat@umich.edu)
* Jordan Huang (jordanhu@umich.edu)

--------

