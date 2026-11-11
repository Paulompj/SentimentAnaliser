"""Classifica a amostra do chat de 2026 com o pipeline Transformers.

Execução: .venv\\Scripts\\python.exe scripts\\classificar_chat_2026.py
O CSV de rotulação manual permanece intacto.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analise_sentimentos.pipelines.transformer_chat import main, load_rows  # noqa: E402,F401


if __name__ == "__main__":
    main()
