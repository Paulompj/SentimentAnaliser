"""Pré-processamento leve para mensagens sociais em português.

Segue as transformações usadas pelo pysentimiento para o modelo BERTweet-PT:
hashtags, menções, URLs, alongamentos, risadas e descrições de emoji.
"""

from __future__ import annotations

import re

import emoji


HASHTAG = re.compile(r"\B#(\w*[a-zA-Z]+\w*)")
CAMEL = re.compile(r"([A-Z]+)")
HANDLE = re.compile(r"@[a-zA-Z0-9_]+")
URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
REPEATED = re.compile(r"(.)\1{2,}")
LAUGHTER = re.compile(r"[ha][ha]+ah[ha]+|kk+", re.IGNORECASE)
EMOJI_TEXT = re.compile(r"\|([^|]+)\|")


def preprocess_social_text(text: str) -> str:
    """Prepara a frase para o classificador preservando o texto bruto no CSV."""
    text = HASHTAG.sub(lambda match: "hashtag " + CAMEL.sub(r" \1", match[1]).strip().lower(), text)
    text = text.translate(str.maketrans({"’": "'", "“": '"', "”": '"', "…": " ", "‼": "!"}))
    text = HANDLE.sub("@USER", text)
    text = URL.sub("HTTPURL", text)
    text = REPEATED.sub(r"\1\1\1", text)
    text = emoji.demojize(text, language="pt", delimiters=("|", "|"))
    text = EMOJI_TEXT.sub(lambda match: " emoji " + match[1].replace("_", " ") + " emoji ", text)
    text = LAUGHTER.sub("kk", text)
    return re.sub(r"\s+", " ", text).strip()
