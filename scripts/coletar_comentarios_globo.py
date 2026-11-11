"""Coleta comentários do vídeo publicado do debate da Globo nas três primeiras horas."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analise_sentimentos.sources.collector import CollectionError, YouTubeCollector, parse_utc  # noqa: E402
from analise_sentimentos.sources.live_chat import video_id_from_url  # noqa: E402


CSV_FIELDS = ["comment_id", "video_id", "text", "published_at", "updated_at",
              "like_count", "reply_count"]


def collect_published_comments(
    video_id: str,
    output: Path,
    *,
    published_at: str | None = None,
    client: YouTubeCollector | None = None,
) -> dict:
    """Faz uma coleta completa após o fim da janela; não executa análise de sentimento."""
    client = client or YouTubeCollector()
    video = client.video(video_id)
    publication = parse_utc(published_at or video.published_at)
    if not published_at and video.live_end_at and publication <= parse_utc(video.live_end_at):
        raise ValueError("A data de publicação da API é anterior ao fim da live. "
                         "Informe --published-at com o horário em que a versão publicada ficou disponível.")
    end = publication + timedelta(hours=3)
    if datetime.now(timezone.utc) < end:
        raise ValueError(f"A janela ainda não terminou. Execute após {end.isoformat()}")
    result = client.collect_window(video_id, publication, end)
    if not result.complete:
        raise CollectionError("Coleta incompleta; CSV não foi substituído")
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "comentarios_pos_publicacao.csv"
    temporary = csv_path.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for comment in result.comments:
            writer.writerow({
                "comment_id": comment.comment_id,
                "video_id": video_id,
                "text": comment.text,
                "published_at": comment.published_at,
                "updated_at": comment.updated_at,
                "like_count": comment.like_count,
                "reply_count": comment.reply_count,
            })
    temporary.replace(csv_path)
    report = {
        "video_id": video_id,
        "video_title": video.title,
        "debate": "Globo 2026",
        "source": "YouTube Data API v3 / commentThreads.list / topLevelComment",
        "window_start_utc": publication.isoformat(),
        "window_end_utc": end.isoformat(),
        "published_at_source": "manual" if published_at else "videos.list snippet.publishedAt",
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "pages": result.pages,
        "inspected": result.inspected,
        "eligible": len(result.comments),
        "edited_after_window": result.edited_after_window,
        "complete": result.complete,
    }
    (output / "comentarios_pos_publicacao_resumo.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="URL ou ID da versão publicada do vídeo do debate da Globo")
    parser.add_argument("--published-at", help="Publicação real ISO 8601 com fuso, se videos.list trouxer horário de live agendada")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "output" / "2026" / "globo")
    args = parser.parse_args(argv)
    try:
        report = collect_published_comments(video_id_from_url(args.video), args.output,
                                            published_at=args.published_at)
    except (CollectionError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Salvos {report['eligible']} comentários em {args.output / 'comentarios_pos_publicacao.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
