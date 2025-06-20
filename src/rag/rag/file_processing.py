import os
import fitz  # PyMuPDF
from typing import Tuple, Optional, Callable
from docx import Document as DocxDocument

def process_file(
    file_bytes: bytes,
    filename: Optional[str] = None,
    ocr_fn: Optional[Callable[[bytes], str]] = None
) -> Tuple[Optional[str], Optional[dict]]:
    """
    Prend un fichier en bytes et retourne le texte extrait + metadata.
    Supporte : .txt, .pdf, .jpg, .png, .webp, .docx
    L'argument ocr_fn permet de passer une fonction OCR (par ex. ocr_call).
    """
    ext = os.path.splitext(filename)[1].lower() if filename else ''
    basename = os.path.splitext(filename)[0] if filename else ''
    metadata = {"filename": basename, "extension": ext}
    
    try:
        # 📄 Fichiers texte brut
        if ext in ['.txt', '.md', '.csv']:
            text = file_bytes.decode('utf-8', errors='ignore')
            return text, metadata

        # 📄 Fichiers DOCX (Word)
        elif ext == '.docx':
            with open(f"/tmp/{basename}.docx", "wb") as f:
                f.write(file_bytes)
            doc = DocxDocument(f"/tmp/{basename}.docx")
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs)
            return text if text else None, metadata

        # 📄 PDF (texte natif ou OCR fallback)
        elif ext == '.pdf':
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            extracted_texts = []
            for page_idx in range(doc.page_count):
                page = doc.load_page(page_idx)
                page_text = page.get_text("text")
                if page_text.strip():
                    extracted_texts.append(page_text)
            if extracted_texts:
                return "\n".join(extracted_texts), metadata
            # Fallback OCR sur chaque page image (si ocr_fn est fourni)
            if ocr_fn:
                ocr_texts = []
                for page_idx in range(doc.page_count):
                    page = doc.load_page(page_idx)
                    pix = page.get_pixmap(dpi=300)
                    img_bytes = pix.tobytes("jpeg")
                    ocr = ocr_fn(img_bytes)
                    if ocr.strip():
                        ocr_texts.append(ocr)
                return "\n".join(ocr_texts) if ocr_texts else None, metadata
            else:
                return None, metadata

        # 🖼️ Images (JPEG, PNG, etc.) : OCR direct (si ocr_fn est fourni)
        elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
            if ocr_fn:
                ocr = ocr_fn(file_bytes)
                return ocr if ocr.strip() else None, metadata
            else:
                return None, metadata

        # ❌ Extension non supportée
        else:
            print(f"[INFO] Extension non supportée : {ext}")
            return None, None

    except Exception as e:
        print(f"[ERREUR] Traitement fichier : {e}")
        return None, None
