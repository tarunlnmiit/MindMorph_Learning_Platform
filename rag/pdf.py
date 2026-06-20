"""PDF text extraction for material ingestion (P2 #9) via PyMuPDF (``fitz``).

Kept tiny and dependency-isolated: ``fitz`` is imported lazily so importing this module (or the
ingest-disabled path) never loads PyMuPDF.
"""
import logging
from typing import Union

logger = logging.getLogger(__name__)


def extract_text_from_pdf(data: Union[bytes, str]) -> str:
    """Extract plain text from a PDF given raw ``bytes`` or a file path.

    Returns the concatenated page text (blank line between pages). Raises ``ValueError`` if the PDF
    can't be opened or yields no text, so callers can surface a clean error.
    """
    import fitz  # lazy: PyMuPDF only when ingesting

    try:
        if isinstance(data, bytes):
            doc = fitz.open(stream=data, filetype="pdf")
        else:
            doc = fitz.open(data)
    except Exception as e:
        raise ValueError(f"could not open PDF: {e}") from e

    try:
        pages = [page.get_text("text").strip() for page in doc]
    finally:
        doc.close()

    text = "\n\n".join(p for p in pages if p)
    if not text.strip():
        raise ValueError("PDF contained no extractable text (scanned image? needs OCR)")
    return text
