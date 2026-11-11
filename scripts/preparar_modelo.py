"""Baixa e verifica a revisão BERTweet usada na classificação dos blocos."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".cache_huggingface"))

    import truststore

    truststore.inject_into_ssl()

    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    from analise_sentimentos.pipelines.band_blocks import MODEL_ID, MODEL_REVISION
    from analise_sentimentos.pipelines.transformer_attribution import LABELS

    print(f"Preparando {MODEL_ID}@{MODEL_REVISION}...", flush=True)
    AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, use_safetensors=True)
    if model.config._commit_hash != MODEL_REVISION:
        raise ValueError("Revisão carregada difere da revisão fixada")
    if set(model.config.id2label.values()) != set(LABELS):
        raise ValueError(f"Classes inesperadas: {model.config.id2label}")
    print("Modelo e tokenizer prontos para a classificação com cache local.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
