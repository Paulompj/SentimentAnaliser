"""
Cliente para a YouTube Data API v3.

Responsável por:
  - Buscar informações de um vídeo (título, canal, views, likes, etc.)
  - Buscar todos os comentários de um vídeo com paginação automática
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from config.settings import (
    COMMENTS_ORDER,
    COMMENTS_PER_PAGE,
    YOUTUBE_API_BASE_URL,
    YOUTUBE_API_KEY,
)


@dataclass
class VideoInfo:
    """Dados resumidos de um vídeo do YouTube."""

    titulo: str
    canal: str
    publicado_em: str
    views: str
    likes: str
    total_comentarios: str


@dataclass
class Comentario:
    """Representa um comentário extraído de um vídeo."""

    autor: str
    texto: str


class YouTubeClient:
    """Cliente HTTP para a YouTube Data API v3."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or YOUTUBE_API_KEY
        if not self._api_key:
            raise ValueError(
                "API key não configurada. "
                "Defina YOUTUBE_API_KEY no arquivo .env"
            )
        self._session = requests.Session()

    # ── Informações do vídeo ─────────────────────────────────────────────

    def buscar_info_video(self, video_id: str) -> VideoInfo | None:
        """Retorna metadados básicos do vídeo ou None em caso de erro."""
        params = {
            "part": "snippet,statistics",
            "id": video_id,
            "key": self._api_key,
        }

        try:
            resp = self._session.get(
                f"{YOUTUBE_API_BASE_URL}/videos", params=params
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f" Não foi possível buscar info do vídeo: {exc}")
            return None

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None

        snippet = items[0]["snippet"]
        stats = items[0]["statistics"]

        return VideoInfo(
            titulo=snippet.get("title", ""),
            canal=snippet.get("channelTitle", ""),
            publicado_em=snippet.get("publishedAt", "")[:10],
            views=stats.get("viewCount", "0"),
            likes=stats.get("likeCount", "0"),
            total_comentarios=stats.get("commentCount", "0"),
        )

    # ── Comentários ──────────────────────────────────────────────────────

    def buscar_comentarios(self, video_id: str) -> list[Comentario]:
        """
        Busca todos os comentários de nível superior de um vídeo.

        Faz paginação automática usando nextPageToken até esgotar
        as páginas disponíveis.
        """
        comentarios: list[Comentario] = []
        next_page_token: str | None = None

        while True:
            params: dict = {
                "part": "snippet",
                "videoId": video_id,
                "key": self._api_key,
                "maxResults": COMMENTS_PER_PAGE,
                "order": COMMENTS_ORDER,
                "textFormat": "plainText",
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            try:
                resp = self._session.get(
                    f"{YOUTUBE_API_BASE_URL}/commentThreads", params=params
                )

                if resp.status_code != 200:
                    print(f" Erro na YouTube API: {resp.status_code}")
                    break

                data = resp.json()
            except requests.RequestException as exc:
                print(f" Erro ao buscar comentários: {exc}")
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                snippet = (
                    item["snippet"]["topLevelComment"]["snippet"]
                )
                autor = snippet.get("authorDisplayName", "")
                texto = snippet.get("textDisplay", "").replace("?", "")

                comentarios.append(Comentario(autor=autor, texto=texto))

            print(f"   {len(comentarios)} comentários coletados...")

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        return comentarios
