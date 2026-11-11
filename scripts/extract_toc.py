"""Extrai texto das primeiras páginas do livro de referência para consulta."""

from pathlib import Path

from PyPDF2 import PdfReader


REFERENCE_DIR = Path(__file__).resolve().parents[1] / "docs" / "referencias"
PDF_PATH = REFERENCE_DIR / "pln_conceitos_tecnicas_aplicacoes_pt_4ed_2026.pdf"


def extract_pages(start: int, stop: int, filename: str) -> Path:
    reader = PdfReader(PDF_PATH)
    content = []
    for index in range(start, min(stop, len(reader.pages))):
        content.append(f"--- Page {index + 1} ---\n")
        content.append((reader.pages[index].extract_text() or "") + "\n")
    destination = REFERENCE_DIR / filename
    destination.write_text("".join(content), encoding="utf-8")
    return destination


if __name__ == "__main__":
    print(extract_pages(0, 25, "toc_output.txt"))
