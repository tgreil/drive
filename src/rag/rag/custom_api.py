import requests
from typing import List
import io
import requests

# Assurez-vous que ces variables sont définies quelque part dans votre projet
URL_API_OCR = "https://your-ocr-api-endpoint"
TIMEOUT = 30

def ocr_call(img_bytes: bytes) -> str:
    """
    Envoie l'image en bytes à l'API OCR et retourne le texte extrait.
    """
    try:
        buf = io.BytesIO(img_bytes)
        files = {"files": ("image.jpg", buf, "image/jpeg")}
        resp = requests.post(URL_API_OCR, files=files, verify=False, timeout=TIMEOUT, proxies={"http": None, "https": None})
        resp.raise_for_status()
        data = resp.json()
        all_texts: List[str] = []
        for info in data.values():
            all_texts.extend(info.get("result", []))
        return "\n".join(all_texts)
    except Exception as e:
        print(f"[ERREUR] OCR : {e}")
        return ""
    
class CustomAPIEmbedder:
    def __init__(self, api_url: str, api_key: str = None):
        self.api_url = api_url
        self.api_key = api_key  # Si tu as besoin d'une clé d'API

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            payload = {"text": text}
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

            response = requests.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()  # Pour lever une exception si erreur HTTP

            embedding = response.json().get("embedding")
            if embedding is None:
                raise ValueError(f"Pas d'embedding dans la réponse API : {response.json()}")

            embeddings.append(embedding)

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
    
embedder = CustomAPIEmbedder(api_url="http://127.0.0.1:8000/embedding", api_key="sk-...")
    

