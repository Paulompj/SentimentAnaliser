"""Extrai as páginas 26 a 50 do livro de referência para consulta."""

from extract_toc import extract_pages


if __name__ == "__main__":
    print(extract_pages(25, 50, "toc_output2.txt"))
