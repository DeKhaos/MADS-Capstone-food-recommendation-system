#################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_NAME = MADS-Capstone-food-recommendation-system
PYTHON_VERSION = 3.11
PYTHON_INTERPRETER = python

#################################################################################
# COMMANDS                                                                      #
#################################################################################


## Install Python dependencies
.PHONY: requirements
requirements:
	$(PYTHON_INTERPRETER) -m pip install -U pip
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt
	
## Environment Setup

.PHONY: env
env:
	@if [ ! -f .env ]; then \
		cp .env_template .env; \
		echo ".env file created from .env_template"; \
	else \
		echo ".env file already exists. Skipping..."; \
	fi


## Delete all compiled Python files
.PHONY: clean
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete


## Lint using flake8, black, and isort (use `make format` to do formatting)
.PHONY: lint
lint:
	flake8 project_package
	isort --check --diff project_package
	black --check project_package

## Format source code with black
.PHONY: format
format:
	isort project_package
	black project_package



## Run tests
.PHONY: test
test:
	python -m pytest tests




#################################################################################
# PROJECT RULES                                                                 #
#################################################################################


## Make dataset
.PHONY: data
data:  # Example command
	$(PYTHON_INTERPRETER) project_package/data_collection/example_dataset.py


#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

define PRINT_HELP_PYSCRIPT
import re, sys; \
lines = '\n'.join([line for line in sys.stdin]); \
matches = re.findall(r'\n## (.*)\n[\s\S]+?\n([a-zA-Z_-]+):', lines); \
print('Available rules:\n'); \
print('\n'.join(['{:25}{}'.format(*reversed(match)) for match in matches]))
endef
export PRINT_HELP_PYSCRIPT

help:
	@$(PYTHON_INTERPRETER) -c "${PRINT_HELP_PYSCRIPT}" < $(MAKEFILE_LIST)
