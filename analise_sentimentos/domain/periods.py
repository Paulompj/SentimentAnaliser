"""Marcos temporais do debate e da discussão inicial no vídeo."""

from datetime import datetime, timedelta


DEBATE_START_UTC = "2022-10-16T23:00:00Z"
DEBATE_END_UTC = "2022-10-17T00:52:18Z"
# Valor registrado pela API em 18/10/2026; usado quando a fonte é um CSV externo.
VIDEO_PUBLISHED_AT_UTC = "2022-10-17T01:06:39Z"
HOURS_AFTER_PUBLICATION = 3
PERIODS = ("durante_debate", "entre_debate_e_publicacao", "apos_publicacao")


def window_end(publication: datetime) -> datetime:
    """Inclui a marca exata de três horas após a publicação."""
    return publication + timedelta(hours=HOURS_AFTER_PUBLICATION)


def period_of(comment: datetime, debate_end: datetime, publication: datetime) -> str:
    if comment <= debate_end:
        return "durante_debate"
    if comment < publication:
        return "entre_debate_e_publicacao"
    return "apos_publicacao"
