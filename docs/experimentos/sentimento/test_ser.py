import nltk
from nltk.corpus import wordnet as wn
from nltk.corpus import sentiwordnet as swn

# Baixa dependências se necessário
nltk.download('wordnet', quiet=True)
nltk.download('sentiwordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)
nltk.download('omw-2.0', quiet=True)

# Busca synsets de "ser" em português como verbo (v)
synsets = list(wn.synsets("ser", lang='por', pos=wn.VERB))
print(f"Synsets encontrados para 'ser': {len(synsets)}")

for s in synsets:
    try:
        senti = swn.senti_synset(s.name())
        print(f"Synset: {s.name()}")
        print(f"  Definição: {s.definition()}")
        print(f"  Pos: {senti.pos_score():.3f} | Neg: {senti.neg_score():.3f} | Obj: {senti.obj_score():.3f}")
    except Exception as e:
        print(f"  Erro no synset {s.name()}: {e}")
