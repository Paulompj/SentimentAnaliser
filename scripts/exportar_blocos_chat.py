"""Exporta um CSV por bloco marcado, preservando o chat bruto original."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from contextlib import ExitStack
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analise_sentimentos.sources.collector import parse_utc  # noqa: E402
from analise_sentimentos.sources.live_chat import CSV_FIELDS  # noqa: E402


def safe_name(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name)
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")[:48] or "bloco"


def export_blocks(output: Path) -> list[dict]:
    blocks = json.loads((output / "blocos.json").read_text(encoding="utf-8"))
    if not isinstance(blocks, list):
        raise ValueError("blocos.json deve conter uma lista")
    closed = [block for block in blocks if block.get("ended_at_utc")]
    if not closed:
        raise ValueError("Nenhum bloco encerrado para exportar")
    ranges = []
    for block in closed:
        start = parse_utc(block["started_at_utc"])
        end = parse_utc(block["ended_at_utc"])
        if start >= end:
            raise ValueError(f"Intervalo inválido para o bloco {block['name']}")
        ranges.append((block, start, end))

    destination = output / "blocos"
    destination.mkdir(parents=True, exist_ok=True)
    report = []
    with (output / "chat_ao_vivo.csv").open(encoding="utf-8-sig", newline="") as source, ExitStack() as stack:
        reader = csv.DictReader(source)
        if not set(CSV_FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("chat_ao_vivo.csv não possui as colunas esperadas")
        writers = []
        for block, start, end in ranges:
            filename = f"{safe_name(block['name'])}_{block['id'][:8]}.csv"
            target = destination / filename
            temporary = target.with_suffix(".csv.tmp")
            file = stack.enter_context(temporary.open("w", encoding="utf-8-sig", newline=""))
            writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
            writer.writeheader()
            entry = {"name": block["name"], "file": filename,
                     "started_at_utc": start.isoformat(), "ended_at_utc": end.isoformat(),
                     "messages": 0}
            report.append(entry)
            writers.append((block, start, end, writer, temporary, target, entry))
        for row in reader:
            published_at = parse_utc(row["published_at"])
            for block, start, end, writer, _, _, entry in writers:
                if row["video_id"] == block["video_id"] and start <= published_at < end:
                    writer.writerow(row)
                    entry["messages"] += 1
    for _, _, _, _, temporary, target, _ in writers:
        temporary.replace(target)
    (destination / "resumo_blocos.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output" / "2026")
    args = parser.parse_args(argv)
    try:
        result = export_blocks(args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    for block in result:
        print(f"{block['name']}: {block['messages']} mensagens em {args.output / 'blocos' / block['file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
