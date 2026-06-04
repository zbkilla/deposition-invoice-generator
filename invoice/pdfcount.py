"""Page counting. This is the whole reason the tool is cheap: it reads only a
PDF's internal structure to get the page count -- no text, no images, nothing
is sent to an AI model. A 5,000-page transcript costs the same as a 5-page
exhibit and never touches your token/coin budget."""

from pathlib import Path

from pypdf import PdfReader


def count_pages(pdf_path: str | Path) -> int:
    reader = PdfReader(str(pdf_path))
    if reader.is_encrypted:
        # Many court PDFs are "encrypted" with an empty owner password.
        reader.decrypt("")
    return len(reader.pages)
