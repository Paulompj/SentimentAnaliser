"""Linha de base léxica de sentimento geral em português.

O modelo spaCy fornece lemas e classes gramaticais. Os escores vêm do
SentiWordNet; o modelo não foi treinado para sentimento ou posição política.
"""

from functools import lru_cache

import spacy
from nltk.corpus import sentiwordnet as swn
from nltk.corpus import stopwords
from nltk.corpus import wordnet as wn


# Falhar explicitamente é preferível a classificar tudo como neutro sem modelo.
nlp = spacy.load("pt_core_news_lg")

POS_MAP = {"ADJ": wn.ADJ, "VERB": wn.VERB, "NOUN": wn.NOUN, "ADV": wn.ADV}
NEGATORS = {"não", "nao", "nunca", "jamais", "nem"}
CLAUSE_BREAKS = {"mas", "porém", "porem", "contudo", "entretanto"}
NEUTRAL_MARGIN = 0.10


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    return frozenset(stopwords.words("portuguese"))


@lru_cache(maxsize=50000)
def _word_scores(lemma: str, pos: str) -> tuple[float, float, tuple[tuple, ...]]:
    wn_pos = POS_MAP[pos]
    synsets = wn.synsets(lemma, pos=wn_pos, lang="por")
    if not synsets:
        synsets = wn.synsets(lemma, lang="por")
    scored = []
    for synset in synsets:
        try:
            score = swn.senti_synset(synset.name())
        except (KeyError, ValueError):
            continue
        if score.obj_score() < 1:
            scored.append((synset.name(), score.pos_score(), score.neg_score(), score.obj_score()))
    if not scored:
        return 0.0, 0.0, ()
    # A média impede que palavras com muitos sentidos dominem só pelo número
    # de synsets; ela ainda não resolve a escolha do sentido no contexto.
    return (
        sum(item[1] for item in scored) / len(scored),
        sum(item[2] for item in scored) / len(scored),
        tuple(scored),
    )


def _is_negated(tokens, index: int) -> bool:
    """Heurística local: negação até três tokens antes, na mesma oração."""
    for previous in range(index - 1, max(-1, index - 4), -1):
        token = tokens[previous]
        if token.is_punct or token.lower_ in CLAUSE_BREAKS:
            break
        if token.lower_ in NEGATORS:
            return True
    return False


def pre_processamento(texto: str) -> str:
    """Preserva pontuação, emoji e negação para a análise contextual."""
    return texto.strip()


def classificador_gramatical(texto: str):
    """Retorna (texto, lema, POS) para inspeção da saída do spaCy."""
    return [(token.text, token.lemma_, token.pos_) for token in nlp(texto)]


def Polarity(textPT: str) -> dict:
    """Classifica sentimento geral; não atribui posição a candidatos."""
    texto = pre_processamento(textPT or "")
    if not texto:
        return {"classificacao": "insufficient_evidence", "pos_total": 0.0,
                "neg_total": 0.0, "detalhes": []}

    tokens = nlp(texto)
    stops = _stopwords()
    pos_total = neg_total = 0.0
    details = []

    for index, token in enumerate(tokens):
        if token.pos_ not in POS_MAP or token.is_space or token.is_punct:
            continue
        if token.lower_ in NEGATORS:
            continue
        lemma = token.lemma_.casefold()
        if lemma in stops:
            continue
        pos, neg, synsets = _word_scores(lemma, token.pos_)
        negated = _is_negated(tokens, index) if synsets else False
        if negated:
            pos, neg = neg, pos
        pos_total += pos
        neg_total += neg
        details.append({
            "indice_token": index,
            "palavra": token.text,
            "lema": lemma,
            "classe_gramatical": token.pos_,
            "negado": negated,
            "pos_score": pos,
            "neg_score": neg,
            "synsets": [
                {"synset": name, "pos": syn_pos, "neg": syn_neg, "obj": obj}
                for name, syn_pos, syn_neg, obj in synsets
            ],
        })

    strength = pos_total + neg_total
    if strength == 0:
        label = "insufficient_evidence"
    elif abs(pos_total - neg_total) / strength <= NEUTRAL_MARGIN:
        label = "neutral"
    elif pos_total > neg_total:
        label = "positive"
    else:
        label = "negative"

    return {"classificacao": label, "pos_total": pos_total,
            "neg_total": neg_total, "detalhes": details}
