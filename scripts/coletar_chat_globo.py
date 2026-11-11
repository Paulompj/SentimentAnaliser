"""Salva o chat ao vivo do debate da Globo em output/2026/globo/chat_ao_vivo.csv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analise_sentimentos.sources.collector import CollectionError  # noqa: E402
from analise_sentimentos.sources.live_chat import collect_live_chat, mark_chat_state, video_id_from_url  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="URL ou ID da transmissão do debate da Globo no YouTube")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output" / "2026" / "globo",
                        help="Pasta exclusiva do debate da Globo (padrão: output/2026/globo)")
    parser.add_argument("--max-wait-minutes", type=float, default=120,
                        help="Tempo máximo para o chat ficar ativo; padrão: 120")
    parser.add_argument("--check-interval", type=float, default=15,
                        help="Intervalo para verificar se a live começou; padrão: 15s")
    parser.add_argument("--min-poll-seconds", type=float, default=3,
                        help="Intervalo mínimo entre páginas do chat; padrão: 3s")
    args = parser.parse_args(argv)
    try:
        video_id = video_id_from_url(args.video)
        result = collect_live_chat(video_id, args.output,
                                   max_wait_minutes=args.max_wait_minutes,
                                   check_interval_seconds=args.check_interval,
                                   min_poll_seconds=args.min_poll_seconds)
    except KeyboardInterrupt:
        if "video_id" in locals():
            mark_chat_state(args.output, video_id, "paused", "Coleta interrompida; pode ser retomada")
        print("Coleta interrompida. CSV e estado preservados; rode o mesmo comando para retomar.", file=sys.stderr)
        return 130
    except (CollectionError, OSError, ValueError) as exc:
        if "video_id" in locals():
            try:
                mark_chat_state(args.output, video_id, "error", str(exc))
            except (OSError, ValueError):
                pass
        parser.error(str(exc))
    print(f"Finalizado: {result.get('total_messages', 0)} mensagens em {args.output / 'chat_ao_vivo.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
