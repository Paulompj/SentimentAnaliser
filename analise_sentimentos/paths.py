"""Localiza os dados na raiz do projeto, inclusive em instalação editável."""

from pathlib import Path

_CHECKOUT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = _CHECKOUT_ROOT if (_CHECKOUT_ROOT / "pyproject.toml").is_file() else Path.cwd()
