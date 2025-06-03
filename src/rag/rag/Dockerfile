FROM python:latest

RUN pip install langchain pymupdf python-docx requests typing tiktoken boto3

run mkdir /rag

COPY file_processing.py /rag
COPY get_file.py /rag
COPY ocr_api.py /rag