"""
Análise de polaridade de sentimento usando SentiWordNet.

Tokeniza o texto em inglês, identifica a POS tag de cada palavra,
consulta o SentiWordNet e acumula os scores positivo/negativo
para determinar a polaridade final do comentário.
"""

from nltk.corpus import sentiwordnet as swn
from nltk.tag.perceptron import PerceptronTagger
from nltk.tokenize import word_tokenize
from operator import itemgetter


# Mapeamento de POS tags do Penn Treebank para as categorias do WordNet
POS_MAP = {
    "JJ": "a",   # adjetivo
    "VBP": "v",  # verbo presente
    "VBZ": "v",  # verbo 3ª pessoa singular
    "VBN": "v",  # particípio passado
    "VBG": "v",  # gerúndio
    "VBD": "v",  # verbo passado
    "NN": "n",   # substantivo
    "RB": "r",   # advérbio
}

# Tags que queremos analisar
RELEVANT_TAGS = set(POS_MAP.keys())


def Polarity(textEN: str) -> str:
    """
    Calcula a polaridade de sentimento de um texto em inglês.

    Retorna:
        'positive', 'negative' ou 'neutral'
        '' em caso de texto vazio ou erro
    """
    try:
        if textEN is None:
            return ''

        textEN = textEN.lower()
        pos = 0.0
        neg = 0.0
        obj = 0.0

        tagger = PerceptronTagger()

        for word, tag in tagger.tag(word_tokenize(textEN)):
            if tag in RELEVANT_TAGS:
                synset = list(swn.senti_synsets(word, POS_MAP[tag]))
                for s in synset:
                    if s.obj_score() < 1:
                        pos += s.pos_score()
                        neg += s.neg_score()
                        obj += s.obj_score()

        if pos == neg:
            return 'neutral'
        else:
            result = [("positive", pos), ("negative", neg)]
            result = sorted(result, key=itemgetter(1), reverse=True)
            result = itemgetter(0)(result[0])
            return result

    except Exception:
        return ''
