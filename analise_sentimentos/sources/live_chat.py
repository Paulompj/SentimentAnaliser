"""Coleta incremental do chat de uma transmissão pública do YouTube."""

from __future__ import annotations

import csv
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from analise_sentimentos.sources.collector import CollectionError, YouTubeCollector


CSV_FIELDS = [
    "message_id", "video_id", "live_chat_id", "published_at", "received_at_utc",
    "message_type", "text", "author_channel_id", "author_name", "author_is_moderator",
    "author_is_owner", "author_is_verified", "author_is_member",
]
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def video_id_from_url(value: str) -> str:
    """Aceita ID, URL watch, youtu.be ou /live/ sem fazer buscas na API."""
    value = value.strip()
    if VIDEO_ID_RE.fullmatch(value):
        return value
    url = urlparse(value)
    host = (url.hostname or "").lower()
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = url.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        parts = url.path.strip("/").split("/")
        if parts[0] == "watch":
            candidate = parse_qs(url.query).get("v", [""])[0]
        elif parts[0] in {"live", "shorts", "embed"} and len(parts) > 1:
            candidate = parts[1]
        else:
            candidate = ""
    else:
        candidate = ""
    if not VIDEO_ID_RE.fullmatch(candidate):
        raise ValueError("Informe um link do YouTube com ID de vídeo válido (11 caracteres)")
    return candidate


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def message_row(item: dict, video_id: str, live_chat_id: str) -> dict:
    snippet = item.get("snippet", {})
    author = item.get("authorDetails", {})
    return {
        "message_id": item["id"],
        "video_id": video_id,
        "live_chat_id": live_chat_id,
        "published_at": snippet.get("publishedAt", ""),
        "received_at_utc": utc_now(),
        "message_type": snippet.get("type", ""),
        "text": snippet.get("textMessageDetails", {}).get("messageText") or snippet.get("displayMessage", ""),
        "author_channel_id": author.get("channelId", ""),
        "author_name": author.get("displayName", ""),
        "author_is_moderator": int(bool(author.get("isChatModerator", False))),
        "author_is_owner": int(bool(author.get("isChatOwner", False))),
        "author_is_verified": int(bool(author.get("isVerified", False))),
        "author_is_member": int(bool(author.get("isChatSponsor", False))),
    }


def _load_state(path: Path, video_id: str) -> dict:
    if not path.exists():
        return {}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("video_id") != video_id:
        raise ValueError("O estado existente pertence a outro vídeo; escolha outra pasta de saída")
    return state


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    # No Windows, o leitor do painel pode manter o destino aberto por um instante.
    # Aguarda esse bloqueio transitório sem perder o estado ou encerrar a coleta.
    for attempt in range(12):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(min(0.05 * (attempt + 1), 0.5))


def mark_chat_state(output: Path, video_id: str, phase: str, message: str = "") -> None:
    """Registra pausa ou erro para o painel sem alterar o CSV."""
    path = output / "chat_estado.json"
    state = _load_state(path, video_id)
    state.update(video_id=video_id, phase=phase, status_updated_at_utc=utc_now(),
                 status_message=message)
    _save_state(path, state)


def _existing_ids(path: Path, video_id: str) -> set[str]:
    if not path.exists():
        return set()
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not {"message_id", "video_id"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV existente não tem colunas de chat esperadas")
        seen = set()
        for row in reader:
            if row["video_id"] != video_id:
                raise ValueError("CSV existente pertence a outro vídeo; escolha outra pasta de saída")
            seen.add(row["message_id"])
        return seen


class LiveChatError(CollectionError):
    def __init__(self, message: str, *, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


def _chat_page(client: YouTubeCollector, live_chat_id: str, page_token: str | None) -> dict:
    params = {
        "part": "id,snippet,authorDetails",
        "liveChatId": live_chat_id,
        "maxResults": 2000,
        "key": client.api_key,
    }
    if page_token:
        params["pageToken"] = page_token
    try:
        response = client.session.get(
            "https://www.googleapis.com/youtube/v3/liveChat/messages",
            params=params,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise LiveChatError(f"Falha de conexão: {type(exc).__name__}") from None
    try:
        data = response.json()
    except ValueError:
        raise LiveChatError(f"Resposta HTTP {response.status_code} sem JSON válido") from None
    if not response.ok:
        errors = data.get("error", {}).get("errors", [])
        reason = errors[0].get("reason", "") if errors else ""
        # Nunca incluir a URL da requisição, que contém a chave da API.
        raise LiveChatError(f"YouTube API respondeu HTTP {response.status_code} ({reason or 'sem motivo'})",
                            reason=reason)
    return data


def _active_chat(client: YouTubeCollector, video_id: str) -> tuple[str | None, bool, str]:
    data = client._get("videos", part="snippet,liveStreamingDetails", id=video_id)
    if not data.get("items"):
        raise CollectionError("Vídeo não encontrado ou indisponível")
    item = data["items"][0]
    details = item.get("liveStreamingDetails", {})
    return details.get("activeLiveChatId"), bool(details.get("actualEndTime")), item.get("snippet", {}).get("title", "")


def collect_live_chat(
    video_id: str,
    output: Path,
    *,
    max_wait_minutes: float = 120,
    check_interval_seconds: float = 15,
    min_poll_seconds: float = 3,
    client: YouTubeCollector | None = None,
    sleep=time.sleep,
    monotonic=time.monotonic,
) -> dict:
    """Espera a live, segue nextPageToken e persiste cada página antes de avançar."""
    if max_wait_minutes < 0 or check_interval_seconds < 1 or min_poll_seconds < 1:
        raise ValueError("Espera máxima deve ser >= 0; intervalos devem ser >= 1 segundo")
    client = client or YouTubeCollector()
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "chat_ao_vivo.csv"
    state_path = output / "chat_estado.json"
    state = _load_state(state_path, video_id)
    seen = _existing_ids(csv_path, video_id)
    if state.get("complete"):
        print(f"Chat já encerrado: {len(seen)} mensagens em {csv_path}", flush=True)
        return state

    state.update(video_id=video_id, phase="starting", complete=False,
                 total_messages=len(seen), pages=state.get("pages", 0),
                 status_updated_at_utc=utc_now(), status_message="Conectando à API")
    _save_state(state_path, state)

    deadline = monotonic() + max_wait_minutes * 60
    live_chat_id = state.get("live_chat_id")
    title = state.get("video_title", "")
    while not live_chat_id:
        live_chat_id, ended, title = _active_chat(client, video_id)
        if ended:
            raise CollectionError("A live já terminou e o chat não está mais disponível pela API")
        if live_chat_id:
            print(f"Chat ativo: {title}", flush=True)
            break
        if monotonic() >= deadline:
            raise CollectionError("Tempo de espera esgotado sem chat ativo; nenhum dado foi perdido do CSV")
        state.update(phase="waiting_for_live", video_title=title,
                     last_check_at_utc=utc_now(), status_updated_at_utc=utc_now(),
                     status_message="Aguardando o chat ficar ativo")
        _save_state(state_path, state)
        print(f"Aguardando chat ficar ativo; nova verificação em {check_interval_seconds:g}s", flush=True)
        sleep(check_interval_seconds)

    page_token = state.get("next_page_token")
    state.update(video_id=video_id, video_title=title, live_chat_id=live_chat_id,
                 phase="collecting", complete=False, coverage_verified=False,
                 status_updated_at_utc=utc_now(), status_message="Chat ativo; coletando mensagens",
                 started_at_utc=state.get("started_at_utc") or utc_now())
    _save_state(state_path, state)
    failures = 0
    with csv_path.open("a", encoding="utf-8-sig" if not csv_path.exists() else "utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        if file.tell() == 0:
            writer.writeheader()
            file.flush()
            os.fsync(file.fileno())
        while True:
            try:
                data = _chat_page(client, live_chat_id, page_token)
            except LiveChatError as exc:
                if exc.reason == "liveChatEnded":
                    state.update(phase="finished", complete=True, ended_at_utc=utc_now(),
                                 end_reason="liveChatEnded", status_updated_at_utc=utc_now(),
                                 status_message="Chat encerrado pela API")
                    _save_state(state_path, state)
                    break
                if exc.reason in {"quotaExceeded", "dailyLimitExceeded", "liveChatDisabled", "liveChatNotFound", "forbidden"}:
                    raise
                failures += 1
                if failures >= 5:
                    raise LiveChatError(f"Cinco falhas seguidas; CSV preservado. Última: {exc}", reason=exc.reason) from None
                delay = max(check_interval_seconds, 10 * failures)
                print(f"Falha temporária: {exc}. Tentando novamente em {delay:g}s", flush=True)
                sleep(delay)
                continue
            failures = 0
            rows = []
            for item in data.get("items", []):
                message_id = item.get("id")
                if not message_id or message_id in seen:
                    continue
                rows.append(message_row(item, video_id, live_chat_id))
                seen.add(message_id)
            writer.writerows(rows)
            file.flush()
            os.fsync(file.fileno())
            next_token = data.get("nextPageToken")
            if not next_token and not data.get("offlineAt"):
                raise CollectionError("Resposta do chat sem nextPageToken; CSV preservado para retomada")
            page_token = next_token or page_token
            recent_batches = state.get("recent_batches", [])
            recent_batches.append({"at_utc": utc_now(), "messages": len(rows)})
            state.update(next_page_token=page_token, last_response_at_utc=utc_now(),
                         phase="collecting", status_updated_at_utc=utc_now(),
                         status_message="Coletando mensagens", last_batch_messages=len(rows),
                         total_messages=len(seen), pages=state.get("pages", 0) + 1,
                         recent_batches=recent_batches[-30:])
            if rows:
                state["last_message_at_utc"] = rows[-1]["published_at"]
            if not state.get("first_response_at_utc"):
                state["first_response_at_utc"] = state["last_response_at_utc"]
            if data.get("offlineAt"):
                state.update(phase="finished", complete=True, ended_at_utc=data["offlineAt"],
                             end_reason="offlineAt", status_message="Transmissão encerrada")
            _save_state(state_path, state)
            print(f"Chat: +{len(rows)} mensagens | total {len(seen)} | páginas {state['pages']}", flush=True)
            if state.get("complete"):
                break
            interval_ms = data.get("pollingIntervalMillis", 5000)
            sleep(max(min_poll_seconds, float(interval_ms) / 1000))
    return state
