"""Valida os CSVs BERTweet e prepara os dados do painel /resultados."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analise_sentimentos.pipelines.bertweet_validation import AUDIT_DIR, write_audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", type=Path, default=AUDIT_DIR)
    parser.add_argument("--sem-inferencia", action="store_true", help="Só confere arquivos e regras; não executa o modelo")
    args = parser.parse_args()
    report = write_audit(args.saida, inference=not args.sem_inferencia)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
