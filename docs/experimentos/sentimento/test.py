import spacy
import re
from nltk.corpus import stopwords
from nltk.corpus import sentiwordnet as swn
from nltk.corpus import wordnet as wn
from operator import itemgetter

try:
    nlp = spacy.load("pt_core_news_lg")
except Exception:
    nlp = None

mapa_pos = {
    "ADJ": wn.ADJ,
    "VERB": wn.VERB,
    "NOUN": wn.NOUN,
    "ADV": wn.ADV,
}

def pre_processamento(texto):
    texto_limpo = re.sub(r'[^\w\s]|_', '', texto)
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo).strip()
    return texto_limpo

def classificador_gramatical(texto):
    if not nlp:
        return []
    texto = texto.lower()    
    documento = nlp(texto)
    palavras_classificadas_gramaticalmente = []
    for token in documento:
        palavras_classificadas_gramaticalmente.append((token.text, token.lemma_, token.pos_))
    return palavras_classificadas_gramaticalmente

def remover_stopwords(tokens):
    stop_words = set(stopwords.words('portuguese'))
    return [(lema, pos) for lema, pos in tokens if lema.lower() not in stop_words]

def Polarity(palavras_com_pos):
    try:
        pos_total = 0
        neg_total = 0
        obj_total = 0
        detalhes = []

        for palavra, pos_tag in palavras_com_pos:
            wn_pos = mapa_pos.get(pos_tag)
            word_pos = 0
            word_neg = 0
            word_obj = 0
            if wn_pos:
                synsets = wn.synsets(palavra.lower(), pos=wn_pos, lang='por')
                print(palavra,synsets)
                if not synsets and wn_pos == wn.ADJ:
                    synsets = wn.synsets(palavra.lower(), pos=wn.ADJ_SAT, lang='por')
                if not synsets:
                    synsets = wn.synsets(palavra.lower(), lang='por')
            else:
                synsets = wn.synsets(palavra.lower(), lang='por')
            for syn in synsets:
                senti = swn.senti_synset(syn.name())
                print(palavra,syn.name(),senti.pos_score(),senti.neg_score(),senti.obj_score())
                if senti.obj_score() < 1:
                    word_pos += senti.pos_score()
                    word_neg += senti.neg_score()
                    word_obj += senti.obj_score()
            pos_total += word_pos
            neg_total += word_neg
            obj_total += word_obj
            detalhes.append((palavra, word_pos, word_neg, word_obj))

        if pos_total == neg_total:
            classificacao = 'neutral'
        elif pos_total > neg_total:
            classificacao = 'positive'
        else:
            classificacao = 'negative'

        return {
            'classificacao': classificacao,
            'score_positivo': pos_total,
            'score_negativo': neg_total,
            'score_objetivo': obj_total,
            'detalhes': detalhes
        }
    except Exception as e:
        return None

if __name__ == "__main__":
    texto = 'O candidato foi arrogante e despreparado.'

    texto_processado = pre_processamento(texto)
    print(f"Texto após pré-processamento: {texto_processado}\n")
    
    analise = classificador_gramatical(texto_processado)
    print("Lematizacao:")
    for original, lema, gramatica in analise:
        print(f"  {original:15} -> {lema:15} | {gramatica}")
    print("-" * 50)

    lemas_com_pos = [(lema, pos) for _, lema, pos in analise]
    lemas_filtrados = remover_stopwords(lemas_com_pos)
    print(f"Sem stopwords: {[l for l, _ in lemas_filtrados]}")
    print("-" * 50)

    resultado = Polarity(lemas_filtrados)
    if resultado:
        print("Score por palavra:")
        for palavra, p, n, o in resultado['detalhes']:
            print(f"  {palavra:15} | pos: {p:.4f}  neg: {n:.4f}  obj: {o:.4f}")
        print("-" * 50)
        print(f"Score Total  -> pos: {resultado['score_positivo']:.4f}  neg: {resultado['score_negativo']:.4f}")
        print(f"Polaridade: {resultado['classificacao']}")
