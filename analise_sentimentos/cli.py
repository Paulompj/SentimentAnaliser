"""Analisa comentários do debate até três horas após a publicação do vídeo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from analise_sentimentos.paths import PROJECT_ROOT
from analise_sentimentos.domain.mention_summary import write_mention_summary
from analise_sentimentos.domain.periods import DEBATE_START_UTC, VIDEO_PUBLISHED_AT_UTC, window_end
from analise_sentimentos.domain.targets import detect_targets
from analise_sentimentos.pipelines.wordnet import evaluate, export_details, import_comments, write_outputs
from analise_sentimentos.sources.collector import CollectionError, YouTubeCollector, parse_utc


VIDEO_ID = "iYVk1CeIs60"
def detectar_candidato(texto: str) -> list[str]:
    """Mantém a interface usada nas versões anteriores do projeto."""
    return detect_targets(texto)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("run", "evaluate", "details", "candidates"), default="run")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output", help="Pasta dos resultados")
    parser.add_argument("--input-csv", type=Path, help="CSV externo de chat/comentários já coletados")
    parser.add_argument("--start", default=DEBATE_START_UTC, help="Início ISO 8601 com fuso")
    parser.add_argument("--end", help="Fim ISO 8601 com fuso; padrão: publicação + 3 horas")
    parser.add_argument("--sample-size", type=int, default=500)
    parser.add_argument("--max-pages", type=int, help="Limite para diagnóstico; gera coleta incompleta")
    args = parser.parse_args(argv)

    if args.command == "evaluate":
        try:
            result = evaluate(args.output)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "details":
        try:
            stats = export_details(args.output)
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        print(f"Detalhes: {stats['comments']} comentários, {stats['terms']} termos, {stats['synsets']} synsets")
        print(f"Arquivos: {args.output / 'analise_detalhada.jsonl'} e {args.output / 'synsets.csv'}")
        return 0

    if args.command == "candidates":
        try:
            summary = write_mention_summary(args.output)
        except (OSError, ValueError, KeyError) as exc:
            parser.error(str(exc))
        for row in summary:
            print(f"{row['grupo']}: total={row['total']}, positive={row['positive']}, "
                  f"negative={row['negative']}, neutral={row['neutral']}, "
                  f"insufficient_evidence={row['insufficient_evidence']}")
        print(f"Relatório: {args.output / 'relatorio_por_mencao.md'}")
        return 0

    if args.sample_size < 0 or (args.max_pages is not None and args.max_pages < 1):
        parser.error("--sample-size deve ser >= 0 e --max-pages deve ser >= 1")
    try:
        start = parse_utc(args.start)
        if args.input_csv:
            publication = parse_utc(VIDEO_PUBLISHED_AT_UTC)
            end = parse_utc(args.end) if args.end else window_end(publication)
            if start >= end:
                parser.error("o início deve ser anterior ao fim")
            collection = import_comments(args.input_csv, start, end)
            video = None
            source = f"CSV externo: {args.input_csv.name} (cobertura não verificada)"
        else:
            client = YouTubeCollector()
            video = client.video(VIDEO_ID)
            publication = parse_utc(video.published_at)
            end = parse_utc(args.end) if args.end else window_end(publication)
            if start >= end:
                parser.error("o início deve ser anterior ao fim")
            print(f"Vídeo: {video.title}", flush=True)
            print(f"Publicação na API: {video.published_at}", flush=True)
            print(f"Fim do recorte: {end.isoformat()}", flush=True)
            print(f"Transmissão encerrada: {video.live_end_at}", flush=True)
            collection = client.collect_window(VIDEO_ID, start, end, max_pages=args.max_pages)
            source = "YouTube Data API v3 / commentThreads.list (comentários principais)"
        print(f"Coleta encerrada: {len(collection.comments)} comentários elegíveis. Iniciando análise...", flush=True)
        report = write_outputs(args.output, video, collection, start, end, source, args.sample_size)
    except (CollectionError, OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))

    print(f"Elegíveis: {report['collection']['in_window']}", flush=True)
    print(f"Coleta completa: {report['collection']['complete']}", flush=True)
    print(f"Relatório: {args.output / 'relatorio.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
