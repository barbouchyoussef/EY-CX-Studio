"""Pre-download the ML model weights so they ship inside the image.

Run at build time only, and only when BAKE_MODELS=1 (see the Dockerfile). Left to themselves
these libraries fetch ~1.3 GB on FIRST USE into the container's writable layer, which the VM's
startup script discards on every boot -- so the first document upload after each restart pays
for the whole download.
"""

from sentence_transformers import SentenceTransformer
from docling.utils.model_downloader import download_models
import easyocr

print("baking: sentence-transformers embeddings…")
SentenceTransformer("intfloat/multilingual-e5-small")

print("baking: EasyOCR (Arabic + English)…")
easyocr.Reader(["ar", "en"], gpu=False)

print("baking: docling layout + table models…")
download_models()

print("model bake complete")
