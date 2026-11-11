"""Identificação conservadora de menções explícitas aos candidatos."""

from __future__ import annotations

import re
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return "".join(char for char in text if not unicodedata.combining(char))


# normalize() transforma o texto em minúsculas e remove acentos.
PATTERNS_2022 = {
    "lula": re.compile(r"(?<!\w)(?:lula|luiz\s+inacio|13)(?!\w)"),
    "bolsonaro": re.compile(r"(?<!\w)(?:bolsonaro|jair|bozo|22)(?!\w)"),
}
PATTERNS_2026 = {
    "lula": re.compile(r"(?<!\w)(?:lula|luiz\s+inacio|13)(?!\w)"),
    "flavio_bolsonaro": re.compile(r"(?<!\w)(?:flavio|bolsonaro|22)(?!\w)"),
}
FLAVIO_BOLSONARO = re.compile(r"(?<!\w)flavio\s+bolsonaro(?!\w)")
JAIR_BOLSONARO = re.compile(r"(?<!\w)jair(?:\s+messias)?\s+bolsonaro(?!\w)")


def detect_targets(text: str, *, election_year: int = 2022) -> list[str]:
    """Detecta menções segundo os candidatos do debate escolhido."""
    normalized = normalize(text)
    if election_year == 2022:
        # Flávio não era o candidato neste debate.
        normalized = FLAVIO_BOLSONARO.sub(" ", normalized)
        patterns = PATTERNS_2022
    elif election_year == 2026:
        # Jair não é o candidato neste debate.
        normalized = JAIR_BOLSONARO.sub(" ", normalized)
        patterns = PATTERNS_2026
    else:
        raise ValueError(f"Ano eleitoral sem regras de menção: {election_year}")
    return [name for name, pattern in patterns.items() if pattern.search(normalized)]
