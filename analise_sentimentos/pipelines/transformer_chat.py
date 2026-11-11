"""Pipeline Transformers para classificar amostras de chat em português."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from analise_sentimentos.paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
OUTPUT = ROOT / "output" / "2026"
MODEL_ID = "pysentimiento/bertweet-pt-sentiment"
os.environ.setdefault("HF_HOME", str(ROOT / ".cache_huggingface"))

from analise_sentimentos.pipelines.transformer_attribution import LABELS, attribute_to_candidates
from analise_sentimentos.pipelines.social_preprocessing import preprocess_social_text


def load_rows(source: Path) -> list[dict[str, str]]:
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    needed = {"message_id", "video_id", "published_at", "bloco", "text"}
    if not rows or not needed.issubset(rows[0]):
        raise ValueError("Amostra vazia ou sem as colunas esperadas")
    if len({row["message_id"] for row in rows}) != len(rows):
        raise ValueError("IDs de mensagem repetidos na amostra")
    return rows


def main(
    argv: list[str] | None = None,
    *,
    default_input: Path = OUTPUT / "rotulacao_chat_2026.csv",
    default_output: Path = OUTPUT / "rotulacao_automatica_chat_2026.csv",
    debate: str | None = None,
) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=default_input)
    parser.add_argument("--saida", type=Path, default=default_output)
    parser.add_argument("--lote", type=int, default=24)
    parser.add_argument("--limiar", type=float, default=0.60)
    args = parser.parse_args(argv)
    if args.lote < 1 or not 0 < args.limiar <= 1:
        parser.error("Use lote positivo e limiar entre 0 e 1")
    source = args.entrada.resolve()
    destination = args.saida.resolve()
    if source == destination:
        parser.error("A saída precisa ser diferente da entrada")
    rows = load_rows(source)

    import truststore
    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    truststore.inject_into_ssl()
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    print(f"Carregando {MODEL_ID} (a primeira execução baixa cerca de 540 MB)...", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID, use_safetensors=True)
    model.eval()
    labels = model.config.id2label
    if set(labels.values()) != set(LABELS):
        raise ValueError(f"Classes inesperadas do modelo: {labels}")
    revision = model.config._commit_hash or "nao_informada"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    fields = ["message_id", "video_id", "published_at", "bloco",
              "estrato_amostragem", "text", "texto_entrada_modelo", "sentimento_geral_automatico",
              "prob_negativo", "prob_neutro", "prob_positivo", "confianca_modelo",
              "sentimento_lula_automatico", "sentimento_flavio_automatico",
              "regra_atribuicao", "modelo_id", "modelo_revisao"]
    counts = {name: {} for name in ("sentimento_geral_automatico",
                                    "sentimento_lula_automatico", "sentimento_flavio_automatico")}
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for start in range(0, len(rows), args.lote):
            batch = rows[start:start + args.lote]
            model_texts = [preprocess_social_text(row["text"]) for row in batch]
            encoded = tokenizer(model_texts, padding=True,
                                truncation=True, max_length=128, return_tensors="pt")
            with torch.inference_mode():
                scores = torch.softmax(model(**encoded).logits, dim=-1).tolist()
            for row, model_text, score in zip(batch, model_texts, scores):
                probabilities = {labels[index]: probability for index, probability
                                 in enumerate(score)}
                general = max(probabilities, key=probabilities.get)
                target = attribute_to_candidates(row["text"], probabilities, args.limiar)
                result = {field: row.get(field, "") for field in fields}
                result.update({
                    "texto_entrada_modelo": model_text,
                    "sentimento_geral_automatico": LABELS[general],
                    "prob_negativo": f"{probabilities['NEG']:.6f}",
                    "prob_neutro": f"{probabilities['NEU']:.6f}",
                    "prob_positivo": f"{probabilities['POS']:.6f}",
                    "confianca_modelo": f"{probabilities[general]:.6f}",
                    "modelo_id": MODEL_ID,
                    "modelo_revisao": revision,
                    **target,
                })
                writer.writerow(result)
                for field in counts:
                    label = result[field]
                    counts[field][label] = counts[field].get(label, 0) + 1
            print(f"Classificadas {min(start + args.lote, len(rows))}/{len(rows)}", flush=True)
    temporary.replace(destination)
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "source_sha256": sha256(source.read_bytes()).hexdigest(),
        "rows": len(rows),
        "model_id": MODEL_ID,
        "model_revision": revision,
        "transformers_version": transformers.__version__,
        "torch_version": torch.__version__,
        "minimum_probability_for_candidate_proxy": args.limiar,
        "maximum_model_tokens": 128,
        "preprocessing": "analise_sentimentos.pipelines.social_preprocessing.preprocess_social_text: hashtags, menções, URLs, alongamentos, risadas e emojis em português",
        "counts": counts,
        "method": "Polaridade geral POS/NEG/NEU do texto completo; transferência apenas para menção nominal única. Outras referências ficam incertas ou sem referência.",
        "limitations": "Rótulos automáticos não são verdade de referência. Probabilidades do modelo não medem acurácia; polaridade geral não equivale a apoio político nem a sentimento dirigido a um candidato. A amostra é estratificada e não estima prevalência do chat.",
    }
    if debate is not None:
        metadata["debate"] = debate
    destination.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    print(f"Concluído: {destination}", flush=True)
    print(json.dumps(counts, ensure_ascii=False), flush=True)
