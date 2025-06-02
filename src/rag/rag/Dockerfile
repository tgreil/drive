FROM python:latest

RUN pip install langchain pymupdf python-docx requests typing

run mkdir /rag

COPY custom_api.py /rag
COPY file_processing.py /rag