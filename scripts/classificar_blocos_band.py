"""Classifica todo o chat da Band exportado em output/2026/blocos/."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analise_sentimentos.pipelines.band_blocks import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
