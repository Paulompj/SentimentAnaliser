"""Exporta amostra estratificada por blocos do chat do debate da Globo.

Lê o chat_ao_vivo.csv de output/2026/globo/ e gera a amostra de rotulação
na mesma pasta, pronta para classificação manual ou automática.

Execução:
  .venv\\Scripts\\python.exe scripts\\exportar_blocos_chat_globo.py blocos.json
  (onde blocos.json contém a definição dos blocos do debate da Globo)
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analise_sentimentos.sources.collector import parse_utc  # noqa: E402


GLOBO_OUTPUT = PROJECT_ROOT / "output" / "2026" / "globo"

CSV_FIELDS_IN = ["message_id", "video_id", "live_chat_id", "published_at", "received_at_utc",
                 "message_type", "text", "author_channel_id", "author_name", "author_is_moderator",
                 "author_is_owner", "author_is_verified", "author_is_member"]

CSV_FIELDS_OUT = ["message_id", "video_id", "published_at", "bloco",
                  "estrato_amostragem", "text"]


def load_blocks(path: Path) -> list[dict]:
    """Carrega definição de blocos: lista de {nome, inicio, fim} em ISO 8601."""
    data = json.loads(path.read_text(encoding="utf-8"))
    blocks = data if isinstance(data, list) else data.get("blocos", [])
    for block in blocks:
        if not {"nome", "inicio", "fim"}.issubset(block):
            raise ValueError(f"Bloco inválido — falta nome, inicio ou fim: {block}")
    return blocks


def assign_block(published_at: str, blocks: list[dict]) -> str:
    """Retorna o nome do bloco em que a mensagem cai, ou 'fora_de_bloco'."""
    ts = parse_utc(published_at)
    for block in blocks:
        start = parse_utc(block["inicio"])
        end = parse_utc(block["fim"])
        if start <= ts < end:
            return block["nome"]
    return "fora_de_bloco"


def load_chat(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def stratified_sample(rows: list[dict], per_block: int, seed: int = 42) -> list[dict]:
    """Amostra estratificada: até `per_block` mensagens por bloco."""
    by_block: dict[str, list[dict]] = {}
    for row in rows:
        by_block.setdefault(row["bloco"], []).append(row)
    rng = random.Random(seed)
    sample = []
    for block_name, block_rows in sorted(by_block.items()):
        chosen = rng.sample(block_rows, min(per_block, len(block_rows)))
        sample.extend(chosen)
    return sample


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("blocos", type=Path,
                        help="Arquivo JSON com definição dos blocos do debate da Globo")
    parser.add_argument("--input", type=Path, default=GLOBO_OUTPUT / "chat_ao_vivo.csv",
                        help="CSV do chat ao vivo (padrão: output/2026/globo/chat_ao_vivo.csv)")
    parser.add_argument("--output", type=Path, default=GLOBO_OUTPUT,
                        help="Pasta de saída (padrão: output/2026/globo)")
    parser.add_argument("--por-bloco", type=int, default=100,
                        help="Máximo de mensagens por bloco na amostra (padrão: 100)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    blocks = load_blocks(args.blocos)
    print(f"Blocos carregados: {len(blocks)}", flush=True)
    for b in blocks:
        print(f"  {b['nome']}: {b['inicio']} → {b['fim']}", flush=True)

    messages = load_chat(args.input)
    print(f"Mensagens carregadas: {len(messages)}", flush=True)

    # Atribuir bloco
    for msg in messages:
        msg["bloco"] = assign_block(msg["published_at"], blocks)
        msg["estrato_amostragem"] = msg["bloco"]

    # Filtrar apenas textMessageEvent
    text_msgs = [m for m in messages if m.get("message_type") == "textMessageEvent"]
    print(f"Mensagens de texto: {len(text_msgs)}", flush=True)

    # Contagem por bloco
    block_counts: dict[str, int] = {}
    for msg in text_msgs:
        block_counts[msg["bloco"]] = block_counts.get(msg["bloco"], 0) + 1
    for name, count in sorted(block_counts.items()):
        print(f"  {name}: {count} mensagens", flush=True)

    # Amostragem
    sample = stratified_sample(text_msgs, args.por_bloco, args.seed)
    print(f"Amostra: {len(sample)} mensagens", flush=True)

    # Salvar
    args.output.mkdir(parents=True, exist_ok=True)
    out_path = args.output / "rotulacao_chat_globo.csv"
    tmp = out_path.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS_OUT)
        writer.writeheader()
        for row in sample:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS_OUT})
    tmp.replace(out_path)

    # Metadados
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "debate": "Globo 2026",
        "source_chat": str(args.input),
        "total_messages": len(messages),
        "text_messages": len(text_msgs),
        "sample_size": len(sample),
        "per_block": args.por_bloco,
        "seed": args.seed,
        "blocks": blocks,
        "block_counts": block_counts,
    }
    (args.output / "rotulacao_chat_globo_metadados.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Amostra salva: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
