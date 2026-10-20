FROM python:3.11.17

WORKDIR /capstone_app

RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*
    
COPY --parents project_package dash_app /capstone_app/
COPY pyproject.toml README.md LICENSE setup.cfg /capstone_app/
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN ["mkdir", "-p","/data/model"]

ENV NTLK_DATA_PATH=/data/nltk_data
ENV FLASHRANK_PATH=/data/model/flashrank_models
ENV EMBEDDING_PATH=/data/model/embedding_cache
ENV IN_MEMORY_DATA=chunk
ENV DEVICE=cpu

EXPOSE 8080

ENTRYPOINT ["python","-m","dash_app.app"]