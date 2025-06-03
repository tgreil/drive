import boto3
from botocore.client import Config
import base64

MINIO_ENDPOINT = "http://host.docker.internal:9000/"
MINIO_ACCESS_KEY = "drive"
MINIO_SECRET_KEY = "password"
MINIO_BUCKET_NAME = "drive-media-storage"  # D'après createbuckets

def get_item_from_minio(file_key):
    # Connexion à MinIO (S3 compatible)
    s3 = boto3.client(
        's3',
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )

    # Télécharger le fichier en mémoire
    try:
        response = s3.get_object(Bucket=MINIO_BUCKET_NAME, Key=file_key)
        content = response['Body'].read()
    except s3.exceptions.NoSuchKey:
        print(f"Le fichier {file_key} n'existe pas dans le bucket {MINIO_BUCKET_NAME}.")
        return None

    # Encoder le contenu en base64
    encoded_content = base64.b64encode(content).decode('utf-8')

    # Extraire le filename (dernière partie du chemin)
    filename = file_key.split('/')[-1]

    return {
        'filename': filename,
        'content_base64': encoded_content
    }