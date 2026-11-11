"""Classifica a amostra do chat do debate da Globo com Transformers.

Execução: .venv\\Scripts\\python.exe scripts\\classificar_chat_globo.py
O CSV de rotulação manual permanece intacto.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analise_sentimentos.pipelines.transformer_chat import main as classify_chat  # noqa: E402

GLOBO_OUTPUT = ROOT / "output" / "2026" / "globo"


def main(argv: list[str] | None = None) -> None:
    classify_chat(
        argv,
        default_input=GLOBO_OUTPUT / "rotulacao_chat_globo.csv",
        default_output=GLOBO_OUTPUT / "rotulacao_automatica_chat_globo.csv",
        debate="Globo 2026",
    )


if __name__ == "__main__":
    main()
