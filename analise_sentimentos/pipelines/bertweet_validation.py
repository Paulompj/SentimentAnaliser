"""Audita as saídas BERTweet sem substituir as previsões originais."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import re

import emoji

from analise_sentimentos.paths import PROJECT_ROOT
from analise_sentimentos.pipelines.band_blocks import (
    MODEL_ID, MODEL_REVISION, MAX_TOKENS, SOURCE_DIR, OUTPUT_DIR,
    file_hash, infer_batch, load_blocks,
)
from analise_sentimentos.pipelines.social_preprocessing import preprocess_social_text
from analise_sentimentos.pipelines.transformer_attribution import LABELS, attribute_to_candidates

AUDIT_DIR = PROJECT_ROOT / "output" / "2026" / "bertweet_validacao"
IRONY_WORDS = re.compile(r"\bsqn\b|s[oó] que n[aã]o|\baham\b|\bconfia\b", re.I)
IRONY_EMOJIS = {"🙄", "🤡"}


def language_features(text: str) -> dict:
    emojis = [item["emoji"] for item in emoji.emoji_list(text)]
    cues = [match.group() for match in IRONY_WORDS.finditer(text)]
    cues.extend(item for item in emojis if item in IRONY_EMOJIS)
    return {"emojis": emojis, "irony_cues": list(dict.fromkeys(cues))}


def check_prediction(row: dict) -> list[str]:
    """Verifica coerência numérica e regras; não estima acurácia humana."""
    issues = []
    try:
        probabilities = {label: float(row[field]) for label, field in (
            ("NEG", "prob_negativo"), ("NEU", "prob_neutro"), ("POS", "prob_positivo"))}
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
            return ["probabilidade_invalida"]
        if abs(sum(probabilities.values()) - 1) > 0.000003:
            issues.append("soma_probabilidades")
        best = max(probabilities, key=probabilities.get)
        if LABELS[best] != row["sentimento_geral_automatico"]:
            issues.append("rotulo_argmax")
        if abs(float(row["confianca_modelo"]) - probabilities[best]) > 0.000002:
            issues.append("confianca")
        if row["texto_entrada_modelo"] != preprocess_social_text(row["texto_classificado"]):
            issues.append("preprocessamento")
        expected = attribute_to_candidates(row["texto_classificado"], probabilities)
        if any(row[key] != value for key, value in expected.items()):
            issues.append("atribuicao_candidato")
        if row["modelo_id"] != MODEL_ID or row["modelo_revisao"] != MODEL_REVISION:
            issues.append("modelo_revisao")
        if int(row["truncado_128"]) != int(int(row["tokens_antes_corte"]) > MAX_TOKENS):
            issues.append("truncamento")
    except (ValueError, TypeError, KeyError):
        issues.append("campos_invalidos")
    return issues


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def audit_files(source_dir: Path = SOURCE_DIR, result_dir: Path = OUTPUT_DIR) -> tuple[dict, list[dict]]:
    regular, paid, excluded, manifest = load_blocks(source_dir)
    report = json.loads((result_dir / "execucao.json").read_text(encoding="utf-8"))
    errors: Counter = Counter()
    examples = []

    def issue(kind: str, message_id: str = "") -> None:
        errors[kind] += 1
        if len(examples) < 20:
            examples.append({"issue": kind, "message_id": message_id})

    for block in manifest:
        recorded = next((item for item in report["source_manifest"] if item["arquivo"] == block["arquivo"]), None)
        if recorded != block:
            issue("hash_ou_manifesto_origem", block["arquivo"])
    if report.get("source_index_sha256") != file_hash(source_dir / "resumo_blocos.json"):
        issue("hash_indice_blocos")
    expected_groups = [
        ("classificacao.csv", {m.row["message_id"]: m for m in regular}),
        ("superchats_classificados.csv", {m.row["message_id"]: m for m in paid}),
        ("nao_classificados.csv", {m["message_id"]: m for m in excluded}),
    ]
    records = []
    seen = set()
    hashes = {}
    for filename, expected in expected_groups:
        path = result_dir / filename
        hashes[filename] = file_hash(path)
        rows = read_csv(path)
        ids = [row["message_id"] for row in rows]
        if set(ids) != set(expected):
            issue("cobertura_ids", filename)
        for row in rows:
            message_id = row["message_id"]
            if message_id in seen:
                issue("id_duplicado", message_id)
            seen.add(message_id)
            original = expected.get(message_id)
            if original is None:
                continue
            if filename == "nao_classificados.csv":
                if row != original:
                    issue("exclusao_divergente", message_id)
                continue
            if (row["texto_classificado"] != original.text or
                    row["text_original"] != original.row["text"] or row["bloco"] != original.bloco or
                    any(row[key] != original.row[key] for key in ("video_id", "published_at", "message_type"))):
                issue("texto_ou_metadados_divergentes", message_id)
            for kind in check_prediction(row):
                issue(kind, message_id)
            records.append({
                "id": message_id, "block": row["bloco"], "paid": filename.startswith("superchats"),
                "text": row["texto_classificado"], "prepared": row["texto_entrada_modelo"],
                "label": row["sentimento_geral_automatico"],
                "p": [float(row[key]) for key in ("prob_negativo", "prob_neutro", "prob_positivo")],
                "confidence": float(row["confianca_modelo"]),
                "lula": row["sentimento_lula_automatico"], "flavio": row["sentimento_flavio_automatico"],
                "rule": row["regra_atribuicao"], "truncated": bool(int(row["truncado_128"])),
                **language_features(row["texto_classificado"]),
            })
    summary_rows = read_csv(result_dir / "resumo_blocos.csv")
    for summary in summary_rows:
        block = summary["bloco"]
        for is_paid, suffix in ((False, "texto"), (True, "superchat")):
            counts = Counter(r["label"] for r in records if r["block"] == block and r["paid"] == is_paid)
            for label in LABELS.values():
                if int(summary[f"{label}_{suffix}"]) != counts[label]:
                    issue("resumo_blocos_divergente", block)
    recorded_blocks = {item["bloco"]: item for item in report["blocks"]}
    if len(summary_rows) != len(manifest) or {r["bloco"] for r in summary_rows} != set(recorded_blocks):
        issue("inventario_resumo_blocos")
    for row in summary_rows:
        historical = recorded_blocks.get(row["bloco"], {})
        if any(str(historical.get(key)) != value for key, value in row.items()):
            issue("resumo_json_divergente", row["bloco"])
    counts = {"total": len(seen), "regular": len(regular), "paid": len(paid), "excluded": len(excluded)}
    for key, value in (("total_messages", counts["total"]), ("common_text_messages", len(regular)),
                       ("superchats_with_comment", len(paid)), ("excluded_messages", len(excluded))):
        if report.get(key) != value:
            issue("contagem_execucao", key)
    manual = read_csv(PROJECT_ROOT / "output/2026/rotulacao_chat_2026.csv")
    annotated = sum(bool(row["sentimento_lula"] or row["sentimento_flavio"]) for row in manual)
    input_paths = [source_dir / block["arquivo"] for block in manifest]
    input_paths.extend([source_dir / "resumo_blocos.json"])
    input_paths.extend(result_dir / name for name in (
        "classificacao.csv", "superchats_classificados.csv", "nao_classificados.csv", "resumo_blocos.csv", "execucao.json"))
    input_paths.extend(PROJECT_ROOT / name for name in (
        "output/2026/rotulacao_chat_2026.csv", "output/2026/rotulacao_automatica_chat_2026.csv",
        "output/2026/rotulacao_automatica_chat_2026.json", "output/2026/lacunas_coleta.json",
        "analise_sentimentos/pipelines/social_preprocessing.py",
        "analise_sentimentos/pipelines/transformer_attribution.py"))
    result = {"status": "passed" if not errors else "failed", "counts": counts,
              "validated_predictions": len(records), "errors": dict(errors), "error_examples": examples,
              "human_annotated_rows": annotated, "human_sample_rows": len(manual),
              "model_id": MODEL_ID, "revision": MODEL_REVISION,
              "hashes": hashes, "source_manifest": manifest,
              "inputs": {path.relative_to(PROJECT_ROOT).as_posix(): file_hash(path) for path in input_paths},
              "checks": ["Cobertura de IDs e ausência de duplicatas", "Textos e metadados iguais às fontes",
                         "Hashes dos CSVs de origem", "Probabilidades finitas, soma e argmax",
                         "Pré-processamento e regras por candidato", "Modelo, revisão e truncamento",
                         "Conciliação dos resumos CSV e JSON"],
              "accuracy": None, "accuracy_note": "Sem rótulos humanos suficientes: consistência técnica não mede acurácia."}
    return result, records


def diagnostic_cases() -> list[dict]:
    cases = []
    for name in ("Lula", "Flávio"):
        for suffix, description in (
            ("foi muito bem.", "Elogio literal"), ("foi muito bem 👏", "Elogio com aplauso"),
            ("foi muito bem 🙄", "Elogio com possível sinal irônico"),
            ("foi muito bem, só que não.", "Ironia explícita construída"),
            ("é um gênio: só fala besteira 🙄", "Contradição construída"),
            ("falou no debate.", "Descrição sem avaliação"),
            ("falou no debate ❤️", "Descrição com coração"),
            ("falou no debate 🤮", "Descrição com repulsa"),
        ):
            cases.append({"text": f"{name} {suffix}", "description": description, "origin": "synthetic"})
    for text in ("❤️", "👏", "🤡", "🙄", "🇧🇷", "2️⃣2️⃣", "kkkkkkkk"):
        cases.append({"text": text, "description": "Emoji ou risada isolada; alvo não estabelecido", "origin": "synthetic"})
    return cases


def run_inference_validation(records: list[dict]) -> tuple[dict, dict]:
    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, local_files_only=True, use_safetensors=True)
    model.eval()
    reference = read_csv(PROJECT_ROOT / "output/2026/rotulacao_automatica_chat_2026.csv")
    rng = random.Random(20261111)
    sampled = []
    for bucket in ([r for r in records if r["emojis"]], [r for r in records if r["irony_cues"]], records):
        sampled.extend(rng.sample(bucket, min(80, len(bucket))))
    sampled.extend(r for r in records if r["truncated"])
    selected = {r["id"]: r for r in sampled}
    texts = list(dict.fromkeys([r["text"] for r in selected.values()] + [r["text"] for r in reference]))
    cases = diagnostic_cases()
    emoji_rows = rng.sample([r for r in records if r["emojis"]], min(60, sum(bool(r["emojis"]) for r in records)))
    ablations = [{"id": r["id"], "text": r["text"], "without_emoji": emoji.replace_emoji(r["text"], replace=" ").strip()}
                 for r in emoji_rows]
    texts = list(dict.fromkeys(texts + [c["text"] for c in cases] +
                              [c["text"] for c in ablations] + [c["without_emoji"] for c in ablations]))
    predictions = {}
    for start in range(0, len(texts), 16):
        for text, prepared, neg, neu, pos, tokens in infer_batch(texts[start:start + 16], tokenizer, model, torch):
            probabilities = {"NEG": neg, "NEU": neu, "POS": pos}
            predictions[text] = {"prepared": prepared, "p": [neg, neu, pos],
                                 "label": LABELS[max(probabilities, key=probabilities.get)],
                                 "tokens": tokens, "token_pieces": tokenizer.tokenize(prepared)[:128]}
        if (start // 16) % 10 == 0 or start + 16 >= len(texts):
            print(f"Conferência por inferência: {min(start + 16, len(texts))}/{len(texts)} textos", flush=True)
    max_delta = 0.0
    mismatches = []
    token_mismatches = 0
    source_by_id = {r["message_id"]: r for name in ("classificacao.csv", "superchats_classificados.csv")
                    for r in read_csv(OUTPUT_DIR / name)}
    for row in list(selected.values()) + [{"id": r["message_id"], "text": r["text"],
            "label": r["sentimento_geral_automatico"],
            "p": [float(r[k]) for k in ("prob_negativo", "prob_neutro", "prob_positivo")]} for r in reference]:
        new = predictions[row["text"]]
        delta = max(abs(a - b) for a, b in zip(new["p"], row["p"]))
        max_delta = max(max_delta, delta)
        if new["label"] != row["label"] or delta > 0.0001:
            mismatches.append({"id": row["id"], "delta": delta})
        stored = source_by_id.get(row["id"])
        if stored and new["tokens"] != int(stored["tokens_antes_corte"]):
            token_mismatches += 1
    for case in cases:
        case.update(predictions[case["text"]])
        case.update(language_features(case["text"]))
    changed = 0
    for case in ablations:
        case["original"] = predictions[case["text"]]
        case["removed"] = predictions[case["without_emoji"]]
        case["changed_label"] = case["original"]["label"] != case["removed"]["label"]
        changed += case["changed_label"]
    result = {"status": "passed" if not mismatches and not token_mismatches else "failed",
              "reference_sample": len(reference), "stratified_result_sample": len(selected),
              "sampling": "Semente 20261111; até 80 com emoji, 80 com pistas, 80 gerais e todos os truncados; grupos podem se sobrepor.",
              "max_probability_delta": max_delta, "tolerance": 0.0001,
              "mismatches": mismatches, "token_count_mismatches": token_mismatches,
              "torch_version": torch.__version__, "transformers_version": transformers.__version__,
              "tokenizer": type(tokenizer).__name__, "tokenizer_normalization": tokenizer.init_kwargs.get("normalization"),
              "unique_inferred_texts": len(predictions)}
    experiments = {"cases": cases, "emoji_ablation": ablations,
                   "emoji_ablation_summary": {"rows": len(ablations), "changed_labels": changed},
                   "note": "Exemplos construídos e remoção de emojis são diagnósticos, não um benchmark de acurácia ou prova de ironia."}
    return result, experiments


def write_audit(destination: Path = AUDIT_DIR, *, inference: bool = True) -> dict:
    audit, records = audit_files()
    if audit["status"] != "passed":
        raise ValueError(f"Auditoria estrutural falhou: {audit['errors']}")
    destination.mkdir(parents=True, exist_ok=True)
    if inference:
        audit["inference"], experiments = run_inference_validation(records)
    else:
        audit["inference"] = {"status": "not_run"}
        experiments = {"cases": [], "emoji_ablation": [], "note": "Inferência não executada."}
    audit["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    if audit["inference"]["status"] == "failed":
        audit["status"] = "failed"
    gaps_path = PROJECT_ROOT / "output/2026/lacunas_coleta.json"
    gaps = json.loads(gaps_path.read_text(encoding="utf-8"))
    payload = {"audit": audit, "records": records, "experiments": experiments, "gaps": gaps,
               "blocks": list(dict.fromkeys(r["block"] for r in records)),
               "sources": [
                   {"title": "Modelo e classes POS/NEG/NEU", "url": "https://huggingface.co/pysentimiento/bertweet-pt-sentiment"},
                   {"title": "Pré-processamento dos autores", "url": "https://github.com/pysentimiento/pysentimiento/blob/master/pysentimiento/preprocessing.py"},
                   {"title": "Sentimento e ironia são tarefas separadas", "url": "https://github.com/pysentimiento/pysentimiento/blob/master/docs/TASKS.md"},
               ]}
    for name, value in (("auditoria.json", audit), ("painel.json", payload)):
        target = destination / name
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        temporary.replace(target)
    return audit
