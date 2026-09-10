from pypdf import PdfReader
from pathlib import Path


def extract_pdf_text(filepath: str) -> str:
    """Extract all text from a PDF file as a single string."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {filepath}")
    reader = PdfReader(str(path))
    blocks = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            blocks.append(text)
    return "\n\n".join(blocks)


def get_all_pages_text(filepath: str) -> list:
    """Extract text from each page of a PDF, returning a list of strings."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {filepath}")
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        pages.append(text if text else "")
    return pages
