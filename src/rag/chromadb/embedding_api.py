import requests
from typing import List


class CustomAPIEmbedder:
    def __init__(self, api_url: str, api_key: str = None):
        self.api_url = api_url
        self.api_key = api_key 

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