FROM python:latest

RUN pip install pip langchain pymupdf python-docx requests typinh

run mkdir /rag

COPY custom_api.py /rag
COPY file_processing.py /rag