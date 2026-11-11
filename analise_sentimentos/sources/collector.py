"""Coleta reproduzível de comentários principais da YouTube Data API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import truststore

# Usa a cadeia de certificados do sistema, necessária neste ambiente Windows.
truststore.inject_into_ssl()

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from analise_sentimentos.config.settings import YOUTUBE_API_BASE_URL, YOUTUBE_API_KEY


class CollectionError(RuntimeError):
    """Falha de coleta sem expor a chave da API na mensagem."""


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Data sem fuso horário: {value}")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    title: str
    published_at: str
    live_start_at: str | None
    live_end_at: str | None
    comment_count: int


@dataclass(frozen=True)
class Comment:
    comment_id: str
    text: str
    published_at: str
    updated_at: str
    like_count: int
    reply_count: int


@dataclass(frozen=True)
class CollectionResult:
    comments: list[Comment]
    pages: int
    inspected: int
    after_window: int
    before_window: int
    edited_after_window: int
    duplicates: int
    complete: bool


class YouTubeCollector:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or YOUTUBE_API_KEY
        if not self.api_key:
            raise CollectionError("YOUTUBE_API_KEY não configurada no .env")
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _get(self, endpoint: str, **params: object) -> dict:
        try:
            response = self.session.get(
                f"{YOUTUBE_API_BASE_URL}/{endpoint}",
                params={**params, "key": self.api_key},
                timeout=30,
            )
        except requests.RequestException as exc:
            # A exceção de requests pode conter a URL, inclusive a chave.
            raise CollectionError(f"Falha de conexão: {type(exc).__name__}") from None
        if not response.ok:
            raise CollectionError(f"YouTube API respondeu HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError:
            raise CollectionError("YouTube API retornou JSON inválido") from None

    def video(self, video_id: str) -> VideoMetadata:
        data = self._get("videos", part="snippet,statistics,liveStreamingDetails", id=video_id)
        if not data.get("items"):
            raise CollectionError("Vídeo não encontrado ou indisponível")
        item = data["items"][0]
        snippet = item["snippet"]
        live = item.get("liveStreamingDetails", {})
        return VideoMetadata(
            video_id=video_id,
            title=snippet.get("title", ""),
            published_at=snippet["publishedAt"],
            live_start_at=live.get("actualStartTime"),
            live_end_at=live.get("actualEndTime"),
            comment_count=int(item.get("statistics", {}).get("commentCount", 0)),
        )

    def collect_window(
        self,
        video_id: str,
        start: datetime,
        end: datetime,
        *,
        max_pages: int | None = None,
    ) -> CollectionResult:
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError("Intervalo inválido: use datas com fuso e início anterior ao fim")
        start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
        comments: list[Comment] = []
        seen: set[str] = set()
        page_token: str | None = None
        pages = inspected = after = before = edited_after = duplicates = 0
        complete = False

        while True:
            params: dict[str, object] = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": 100,
                "order": "time",
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("commentThreads", **params)
            pages += 1
            reached_start = False
            for item in data.get("items", []):
                top = item["snippet"]["topLevelComment"]
                comment_id = top["id"]
                if comment_id in seen:
                    duplicates += 1
                    continue
                seen.add(comment_id)
                inspected += 1
                snippet = top["snippet"]
                published_at = parse_utc(snippet["publishedAt"])
                if published_at > end:
                    after += 1
                    continue
                if published_at < start:
                    before += 1
                    reached_start = True
                    continue
                updated_at = parse_utc(snippet.get("updatedAt", snippet["publishedAt"]))
                if updated_at > end:
                    edited_after += 1
                    continue
                comments.append(Comment(
                    comment_id=comment_id,
                    text=snippet.get("textDisplay", ""),
                    published_at=snippet["publishedAt"],
                    updated_at=snippet.get("updatedAt", snippet["publishedAt"]),
                    like_count=int(snippet.get("likeCount", 0)),
                    reply_count=int(item["snippet"].get("totalReplyCount", 0)),
                ))
            print(f"Páginas: {pages} | examinados: {inspected} | no intervalo: {len(comments)}", flush=True)
            page_token = data.get("nextPageToken")
            if reached_start or not page_token:
                complete = True
                break
            if max_pages is not None and pages >= max_pages:
                break

        comments.sort(key=lambda item: (item.published_at, item.comment_id))
        return CollectionResult(comments, pages, inspected, after, before, edited_after, duplicates, complete)
