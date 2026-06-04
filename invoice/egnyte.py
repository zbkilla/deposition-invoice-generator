"""Locate a job's PDFs on the mounted Egnyte drive and count their pages.

Files are read in place from the drive -- nothing is downloaded, copied, or
added to Egnyte, so this never grows your storage footprint."""

from dataclasses import dataclass
from pathlib import Path

from .pdfcount import count_pages


@dataclass
class FoundDoc:
    doc_type: str          # "transcript" | "exhibit"
    file_path: str
    page_count: int | None  # None when the file could not be read
    error: str | None = None


def collect_documents(cfg: dict, job_id: str) -> list[FoundDoc]:
    root = Path(cfg["egnyte_root"]) / cfg["job_folder"].format(job_id=job_id)
    found: list[FoundDoc] = []
    for doc_type, subdir in (
        ("transcript", cfg["transcript_subdir"]),
        ("exhibit", cfg["exhibit_subdir"]),
    ):
        folder = root / subdir
        if not folder.is_dir():
            continue
        for pdf in sorted(folder.glob("*.pdf")):
            try:
                found.append(FoundDoc(doc_type, str(pdf), count_pages(pdf)))
            except Exception as exc:  # corrupt / locked -> surface it, don't crash
                found.append(FoundDoc(doc_type, str(pdf), None, str(exc)))
    return found
