"""Classificação retomável de todos os blocos do chat da Band em 2026."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
from time import perf_counter

from analise_sentimentos.paths import PROJECT_ROOT
from analise_sentimentos.pipelines.social_preprocessing import preprocess_social_text
from analise_sentimentos.pipelines.transformer_attribution import LABELS, attribute_to_candidates
from analise_sentimentos.pipelines.transformer_chat import MODEL_ID


SOURCE_DIR = PROJECT_ROOT / "output" / "2026" / "blocos"
OUTPUT_DIR = PROJECT_ROOT / "output" / "2026" / "bertweet_band"
SAMPLE_DIR = PROJECT_ROOT / "output" / "2026"
MODEL_REVISION = "726612815d49447cbfe3f55bbfc2993c1f5fad10"
MAX_TOKENS = 128
MINIMUM_PROBABILITY = 0.60
REQUIRED = {"message_id", "video_id", "published_at", "message_type", "text"}
SUPER_CHAT_COMMENT = re.compile(r'^.+? from @[^:\r\n]+: "(?P<comment>.*)"$', re.DOTALL)
PREDICTION_FIELDS = [
    "bloco", "arquivo_origem", "message_id", "video_id", "published_at",
    "message_type", "text_original", "texto_classificado", "texto_entrada_modelo",
    "tokens_antes_corte", "truncado_128", "sentimento_geral_automatico",
    "prob_negativo", "prob_neutro", "prob_positivo", "confianca_modelo",
    "sentimento_lula_automatico", "sentimento_flavio_automatico",
    "regra_atribuicao", "modelo_id", "modelo_revisao",
]
EXCLUDED_FIELDS = ["bloco", "arquivo_origem", "message_id", "video_id",
                   "published_at", "message_type", "text_original", "motivo"]
SUMMARY_FIELDS = [
    "bloco", "arquivo_origem", "total_registros", "mensagens_texto",
    "superchats_com_comentario", "superchats_sem_comentario", "stickers",
    "outros_excluidos", "positivo_texto", "neutro_texto", "negativo_texto",
    "positivo_superchat", "neutro_superchat", "negativo_superchat",
]


@dataclass(frozen=True)
class Message:
    bloco: str
    arquivo_origem: str
    row: dict[str, str]
    text: str


def file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_superchat_comment(display_message: str) -> str | None:
    """Extrai apenas o comentário citado, sem valor pago e identificação do autor."""
    match = SUPER_CHAT_COMMENT.fullmatch(display_message)
    if not match:
        return None
    comment = match.group("comment").strip()
    return comment or None


def load_blocks(source_dir: Path = SOURCE_DIR) -> tuple[list[Message], list[Message], list[dict], list[dict]]:
    """Lê os cinco arquivos declarados no resumo e reconcilia IDs e contagens."""
    index_path = source_dir / "resumo_blocos.json"
    blocks = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(blocks, list) or len(blocks) != 5:
        raise ValueError("Esperados cinco blocos em resumo_blocos.json")
    listed = {entry["file"] for entry in blocks}
    actual = {path.name for path in source_dir.glob("*.csv")}
    if listed != actual:
        raise ValueError(f"Arquivos de blocos divergentes: esperados={listed}, encontrados={actual}")
    regular: list[Message] = []
    paid: list[Message] = []
    excluded: list[dict] = []
    manifest: list[dict] = []
    ids: set[str] = set()
    for entry in blocks:
        filename = entry["file"]
        if Path(filename).name != filename:
            raise ValueError(f"Nome de arquivo inválido: {filename}")
        path = source_dir / filename
        count = 0
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not REQUIRED.issubset(reader.fieldnames or []):
                raise ValueError(f"Colunas ausentes em {filename}: {sorted(REQUIRED - set(reader.fieldnames or []))}")
            for row in reader:
                count += 1
                message_id = row["message_id"]
                if not message_id or message_id in ids:
                    raise ValueError(f"ID vazio ou duplicado em {filename}: {message_id}")
                ids.add(message_id)
                message = Message(entry["name"], filename, row, row["text"])
                kind = row["message_type"]
                if kind == "textMessageEvent":
                    if not message.text.strip():
                        raise ValueError(f"Mensagem de texto vazia: {message_id}")
                    regular.append(message)
                elif kind == "superChatEvent":
                    comment = extract_superchat_comment(message.text)
                    if comment:
                        paid.append(Message(entry["name"], filename, row, comment))
                    else:
                        excluded.append(excluded_row(message, "superchat_sem_comentario_extraivel"))
                else:
                    reason = "sticker_sem_texto_opinativo" if kind == "superStickerEvent" else "tipo_nao_suportado"
                    excluded.append(excluded_row(message, reason))
        if count != entry["messages"]:
            raise ValueError(f"Contagem de {filename}: resumo={entry['messages']}, CSV={count}")
        manifest.append({"bloco": entry["name"], "arquivo": filename, "registros": count,
                         "sha256": file_hash(path)})
    return regular, paid, excluded, manifest


def excluded_row(message: Message, reason: str) -> dict:
    row = message.row
    return {"bloco": message.bloco, "arquivo_origem": message.arquivo_origem,
            "message_id": row["message_id"], "video_id": row["video_id"],
            "published_at": row["published_at"], "message_type": row["message_type"],
            "text_original": row["text"], "motivo": reason}


def open_cache(path: Path, fingerprint: str) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    connection.execute("""CREATE TABLE IF NOT EXISTS predictions (
        text TEXT PRIMARY KEY, prepared TEXT NOT NULL, neg REAL NOT NULL, neu REAL NOT NULL,
        pos REAL NOT NULL, tokens INTEGER NOT NULL)""")
    found = connection.execute("SELECT value FROM metadata WHERE key='fingerprint'").fetchone()
    if found and found[0] != fingerprint:
        connection.close()
        raise ValueError("Checkpoint pertence a outros dados, modelo ou pré-processamento")
    if not found:
        connection.execute("INSERT INTO metadata VALUES ('fingerprint', ?)", (fingerprint,))
        connection.commit()
    return connection


def cached_texts(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT text FROM predictions")}


def infer_batch(texts: list[str], tokenizer, model, torch) -> list[tuple]:
    prepared = [preprocess_social_text(text) for text in texts]
    original_tokens = tokenizer(prepared, add_special_tokens=True, truncation=False,
                                verbose=False)["input_ids"]
    encoded = tokenizer(prepared, padding=True, truncation=True,
                        max_length=MAX_TOKENS, return_tensors="pt")
    with torch.inference_mode():
        scores = torch.softmax(model(**encoded).logits, dim=-1).tolist()
    labels = model.config.id2label
    return [(text, clean, probabilities["NEG"], probabilities["NEU"],
             probabilities["POS"], len(token_ids))
            for text, clean, score, token_ids in zip(texts, prepared, scores, original_tokens)
            for probabilities in [{labels[index]: value for index, value in enumerate(score)}]]


def store_missing(texts: list[str], connection: sqlite3.Connection, tokenizer, model,
                  torch, batch_size: int, *, progress: bool = True) -> int:
    known = cached_texts(connection)
    missing = [text for text in texts if text not in known]
    total = len(missing)
    for start in range(0, total, batch_size):
        batch = missing[start:start + batch_size]
        predicted = infer_batch(batch, tokenizer, model, torch)
        connection.executemany("INSERT OR IGNORE INTO predictions VALUES (?, ?, ?, ?, ?, ?)", predicted)
        connection.commit()
        done = min(start + batch_size, total)
        if progress and (done == total or done // 500 > start // 500):
            print(f"Inferência: {done}/{total} textos novos", flush=True)
    return total


def choose_batch_size(texts: list[str], tokenizer, model, torch) -> tuple[int, dict[str, float]]:
    probe = texts[:96]
    if len(probe) < 24:
        return 8, {}
    infer_batch(probe[:8], tokenizer, model, torch)  # aquecimento
    timings = {}
    for size in (8, 16, 24):
        start = perf_counter()
        for offset in range(0, len(probe), size):
            infer_batch(probe[offset:offset + size], tokenizer, model, torch)
        timings[str(size)] = round(perf_counter() - start, 3)
    selected = min((8, 16, 24), key=lambda size: timings[str(size)])
    print(f"Lotes CPU: {timings}; selecionado {selected}", flush=True)
    return selected, timings


def prediction_for(text: str, connection: sqlite3.Connection) -> dict:
    result = connection.execute("SELECT prepared, neg, neu, pos, tokens FROM predictions WHERE text=?",
                                (text,)).fetchone()
    if result is None:
        raise ValueError("Previsão ausente no checkpoint")
    prepared, neg, neu, pos, tokens = result
    probabilities = {"NEG": neg, "NEU": neu, "POS": pos}
    general = max(probabilities, key=probabilities.get)
    return {"prepared": prepared, "probabilities": probabilities, "general": general,
            "tokens": tokens}


def verify_existing_sample(regular: list[Message], connection: sqlite3.Connection,
                           sample_dir: Path = SAMPLE_DIR) -> dict:
    sample_path = sample_dir / "rotulacao_chat_2026.csv"
    reference_path = sample_dir / "rotulacao_automatica_chat_2026.csv"
    reference_meta = json.loads(reference_path.with_suffix(".json").read_text(encoding="utf-8"))
    if reference_meta["source_sha256"] != file_hash(sample_path):
        raise ValueError("A amostra manual mudou desde as previsões de referência")
    if reference_meta["model_revision"] != MODEL_REVISION:
        raise ValueError("A revisão do modelo difere da referência de 500 mensagens")
    by_id = {message.row["message_id"]: message for message in regular}
    with sample_path.open("r", encoding="utf-8-sig", newline="") as stream:
        sample = list(csv.DictReader(stream))
    with reference_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reference = {row["message_id"]: row for row in csv.DictReader(stream)}
    if len(sample) != 500 or len(reference) != 500:
        raise ValueError("A conferência exige as 500 mensagens da amostra anterior")
    max_delta = 0.0
    for row in sample:
        message_id = row["message_id"]
        message = by_id.get(message_id)
        old = reference.get(message_id)
        if not message or not old or message.text != row["text"]:
            raise ValueError(f"Amostra não corresponde aos blocos: {message_id}")
        predicted = prediction_for(message.text, connection)
        if predicted["prepared"] != old["texto_entrada_modelo"]:
            raise ValueError(f"Pré-processamento divergiu na amostra: {message_id}")
        if LABELS[predicted["general"]] != old["sentimento_geral_automatico"]:
            raise ValueError(f"Rótulo divergiu na amostra: {message_id}")
        for label, field in (("NEG", "prob_negativo"), ("NEU", "prob_neutro"),
                             ("POS", "prob_positivo")):
            delta = abs(predicted["probabilities"][label] - float(old[field]))
            max_delta = max(max_delta, delta)
            if delta > 0.0001:
                raise ValueError(f"Probabilidade divergiu na amostra: {message_id} ({field})")
        target = attribute_to_candidates(message.text, predicted["probabilities"], MINIMUM_PROBABILITY)
        if any(target[field] != old[field] for field in target):
            raise ValueError(f"Atribuição a candidato divergiu na amostra: {message_id}")
    return {"mensagens_conferidas": 500, "maior_diferenca_probabilidade": max_delta,
            "fonte_sha256": file_hash(sample_path)}


def prediction_row(message: Message, connection: sqlite3.Connection) -> dict:
    predicted = prediction_for(message.text, connection)
    probabilities = predicted["probabilities"]
    raw = message.row
    return {
        "bloco": message.bloco, "arquivo_origem": message.arquivo_origem,
        "message_id": raw["message_id"], "video_id": raw["video_id"],
        "published_at": raw["published_at"], "message_type": raw["message_type"],
        "text_original": raw["text"], "texto_classificado": message.text,
        "texto_entrada_modelo": predicted["prepared"],
        "tokens_antes_corte": predicted["tokens"],
        "truncado_128": int(predicted["tokens"] > MAX_TOKENS),
        "sentimento_geral_automatico": LABELS[predicted["general"]],
        "prob_negativo": f"{probabilities['NEG']:.6f}",
        "prob_neutro": f"{probabilities['NEU']:.6f}",
        "prob_positivo": f"{probabilities['POS']:.6f}",
        "confianca_modelo": f"{probabilities[predicted['general']]:.6f}",
        **attribute_to_candidates(message.text, probabilities, MINIMUM_PROBABILITY),
        "modelo_id": MODEL_ID, "modelo_revisao": MODEL_REVISION,
    }


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def summarize(manifest: list[dict], regular: list[dict], paid: list[dict], excluded: list[dict]) -> list[dict]:
    result = []
    for item in manifest:
        block = item["bloco"]
        reg = [row for row in regular if row["bloco"] == block]
        superchats = [row for row in paid if row["bloco"] == block]
        skipped = [row for row in excluded if row["bloco"] == block]
        summary = {key: 0 for key in SUMMARY_FIELDS}
        summary.update(bloco=block, arquivo_origem=item["arquivo"],
                       total_registros=item["registros"], mensagens_texto=len(reg),
                       superchats_com_comentario=len(superchats),
                       superchats_sem_comentario=sum(row["message_type"] == "superChatEvent" for row in skipped),
                       stickers=sum(row["message_type"] == "superStickerEvent" for row in skipped),
                       outros_excluidos=sum(row["message_type"] not in {"superChatEvent", "superStickerEvent"}
                                            for row in skipped))
        for row in reg:
            summary[f"{row['sentimento_geral_automatico']}_texto"] += 1
        for row in superchats:
            summary[f"{row['sentimento_geral_automatico']}_superchat"] += 1
        if len(reg) + len(superchats) + len(skipped) != item["registros"]:
            raise ValueError(f"Contagens não fecham no bloco {block}")
        result.append(summary)
    return result


def run(source_dir: Path = SOURCE_DIR, output_dir: Path = OUTPUT_DIR,
        batch_size: int | None = None) -> dict:
    regular, paid, excluded, manifest = load_blocks(source_dir)
    all_messages = regular + paid
    distinct = list(dict.fromkeys(message.text for message in all_messages))
    print(f"Base: {sum(item['registros'] for item in manifest)} registros; "
          f"{len(regular)} mensagens comuns; {len(paid)} Super Chats com comentário; "
          f"{len(excluded)} excluídos; {len(distinct)} textos distintos", flush=True)
    preprocessing_path = Path(__file__).with_name("social_preprocessing.py")
    fingerprint_data = {"fontes": manifest, "modelo": MODEL_ID, "revisao": MODEL_REVISION,
                        "preprocessamento_sha256": file_hash(preprocessing_path),
                        "limiar": MINIMUM_PROBABILITY, "max_tokens": MAX_TOKENS}
    fingerprint = sha256(json.dumps(fingerprint_data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    output_dir.mkdir(parents=True, exist_ok=True)
    connection = open_cache(output_dir / "checkpoint.sqlite", fingerprint)
    try:
        import truststore
        import torch
        import transformers
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        truststore.inject_into_ssl()
        os.environ.setdefault("HF_HOME", str(PROJECT_ROOT / ".cache_huggingface"))
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        print(f"Carregando {MODEL_ID}@{MODEL_REVISION} do cache local...", flush=True)
        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION,
                                                   local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            MODEL_ID, revision=MODEL_REVISION, use_safetensors=True, local_files_only=True)
        model.eval()
        if set(model.config.id2label.values()) != set(LABELS):
            raise ValueError(f"Classes inesperadas do modelo: {model.config.id2label}")
        if model.config._commit_hash != MODEL_REVISION:
            raise ValueError("Revisão carregada do modelo não corresponde à revisão fixada")
        if batch_size is None:
            batch_size, timings = choose_batch_size(distinct, tokenizer, model, torch)
        else:
            timings = {}
        sample_path = SAMPLE_DIR / "rotulacao_chat_2026.csv"
        with sample_path.open("r", encoding="utf-8-sig", newline="") as stream:
            sample_texts = list(dict.fromkeys(row["text"] for row in csv.DictReader(stream)))
        store_missing(sample_texts, connection, tokenizer, model, torch, batch_size, progress=False)
        validation = verify_existing_sample(regular, connection)
        print(f"Conferência das 500 previsões: OK; maior diferença "
              f"{validation['maior_diferenca_probabilidade']:.8f}", flush=True)
        remaining = store_missing(distinct, connection, tokenizer, model, torch, batch_size)
        if len(cached_texts(connection).intersection(distinct)) != len(distinct):
            raise ValueError("Checkpoint incompleto após inferência")
        common_rows = [prediction_row(message, connection) for message in regular]
        paid_rows = [prediction_row(message, connection) for message in paid]
        summaries = summarize(manifest, common_rows, paid_rows, excluded)
        write_csv(output_dir / "classificacao.csv", PREDICTION_FIELDS, common_rows)
        write_csv(output_dir / "superchats_classificados.csv", PREDICTION_FIELDS, paid_rows)
        write_csv(output_dir / "nao_classificados.csv", EXCLUDED_FIELDS, excluded)
        write_csv(output_dir / "resumo_blocos.csv", SUMMARY_FIELDS, summaries)
        gaps_path = source_dir.parent / "lacunas_coleta.json"
        report = {
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_manifest": manifest,
            "source_index_sha256": file_hash(source_dir / "resumo_blocos.json"),
            "lacunas_coleta_sha256": file_hash(gaps_path) if gaps_path.exists() else None,
            "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
            "torch_version": torch.__version__, "transformers_version": transformers.__version__,
            "preprocessing_sha256": fingerprint_data["preprocessamento_sha256"],
            "maximum_model_tokens": MAX_TOKENS, "batch_size": batch_size,
            "batch_benchmark_seconds": timings, "minimum_candidate_proxy_probability": MINIMUM_PROBABILITY,
            "sample_equivalence": validation,
            "total_messages": sum(item["registros"] for item in manifest),
            "common_text_messages": len(common_rows), "superchats_with_comment": len(paid_rows),
            "excluded_messages": len(excluded), "unique_inference_texts": len(distinct),
            "new_inference_texts_after_sample": remaining,
            "truncated_common_messages": sum(int(row["truncado_128"]) for row in common_rows),
            "truncated_superchats": sum(int(row["truncado_128"]) for row in paid_rows),
            "blocks": summaries,
            "substantive_blocks": [item["bloco"] for item in summaries if item["bloco"] != "1 parte"],
            "interpretation": "Sentimento geral do texto. Atribuições a candidatos são aproximações exploratórias, não apoio político.",
            "coverage_note": "Existe lacuna documentada durante o Bloco 2; proporções descrevem apenas mensagens capturadas.",
            "validation_note": "A equivalência com 500 previsões anteriores não mede acurácia; rótulos humanos estão vazios.",
        }
        temporary = output_dir / "execucao.json.tmp"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output_dir / "execucao.json")
        print(f"Concluído: {output_dir}", flush=True)
        return report
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", type=Path, default=SOURCE_DIR, help="Pasta dos CSVs e resumo_blocos.json")
    parser.add_argument("--saida", type=Path, default=OUTPUT_DIR, help="Pasta nova para as previsões")
    parser.add_argument("--lote", type=int, help="Tamanho do lote; padrão: medido na CPU")
    args = parser.parse_args(argv)
    if args.lote is not None and args.lote < 1:
        parser.error("--lote deve ser positivo")
    source = args.entrada.resolve()
    destination = args.saida.resolve()
    if destination == source or source in destination.parents:
        parser.error("A saída não pode ficar dentro da pasta de origem")
    try:
        run(source, destination, args.lote)
    except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
        parser.error(str(exc))
    return 0
