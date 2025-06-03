import requests
from typing import List
import io
import requests

# Assurez-vous que ces variables sont définies quelque part dans votre projet
URL_API_OCR = "http://host.docker.internal:8000/ocr"  # URL de l'API OCR
TIMEOUT = 60

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
   