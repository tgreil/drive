FROM python:latest

RUN pip install langchain_chroma langchain_community langchain pymupdf python-docx requests typing tiktoken boto3

RUN mkdir /rag

COPY base_function.py /rag
COPY embedding_api.py /rag
COPY vdb_init.py /rag