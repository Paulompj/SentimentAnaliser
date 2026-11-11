import os
import pickle
import nltk
from nltk.corpus import mac_morpho, wordnet as wn, sentiwordnet as swn
from nltk.tokenize import word_tokenize
from operator import itemgetter

# Baixa os pacotes necessários (incluindo o OMW para ter o WordNet em português)
nltk.download('mac_morpho', quiet=True)
nltk.download('sentiwordnet', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True) 
nltk.download('punkt_tab', quiet=True)

# Mapeamento das tags do mac_morpho (Português) para o WordNet/SentiWordNet
type_map = {
    "ADJ": "a",   # Adjetivo
    "V": "v",     # Verbo
    "N": "n",     # Substantivo Comum
    "NPROP": "n", # Substantivo Próprio (nomes de pessoas, lugares)
    "ADV": "r",   # Advérbio
}

 

def get_pt_tagger():
    tagger_path = 'tagger_ptbr.pkl'
    
    # Se o modelo já foi treinado e salvo, carrega ele (instantâneo)
    if os.path.exists(tagger_path):
        with open(tagger_path, 'rb') as f:
            return pickle.load(f)
            
    print("Treinando o robô gramatical em PT-BR pela primeira vez... (Aguarde de 10 a 20 segundos)")
    
    # Pega as sentenças de treino do mac_morpho (Textos da Folha de S. Paulo)
    train_data = mac_morpho.tagged_sents()
    
    # Treina um UnigramTagger (analisa a estatística de cada palavra isolada)
    tagger = nltk.UnigramTagger(train_data)
    
    # Salva o modelo treinado em disco para não precisar treinar de novo depois
    with open(tagger_path, 'wb') as f:
        pickle.dump(tagger, f)
        
    return tagger

def Polarity_PT(textPT):
    try:
        if textPT is not None:
            textPT = textPT.lower()
            pos = 0
            neg = 0
            obj = 0
            
            # 1. Carrega o nosso Tagger em português
            tagger = get_pt_tagger()
            
            # 2. Tokenização (idioma=portuguese) e 3. POS Tagging
            tagged_words = tagger.tag(word_tokenize(textPT, language='portuguese'))
            
            print(f"Palavras classificadas gramaticalmente (PT-BR):")
            print(tagged_words, "\n")
            
            for word, tag in tagged_words:
                # Se a palavra não foi reconhecida pelo tagger, o tag será None
                if tag is not None and tag in type_map:
                    wn_pos = type_map[tag]
                    
                    # 4. Busca no Open Multilingual WordNet (OMW) em português!
                    # Importante: filtramos também pela classe gramatical correta (wn_pos)
                    synsets = list(wn.synsets(word, lang='por', pos=wn_pos))
                    
                    if not synsets:
                        continue
                        
                    for s in synsets:
                        # Passamos o ID do synset para o SentiWordNet descobrir a emoção
                        senti_syn = swn.senti_synset(s.name())
                        if senti_syn.obj_score() < 1: # Ignora notas 100% neutras
                            pos += senti_syn.pos_score()
                            neg += senti_syn.neg_score()
                            obj += senti_syn.obj_score()

            if pos == 0 and neg == 0:
                return 'neutral'
            elif pos == neg:
                return 'neutral'
            else:
                result = [("positive", pos), ("negative", neg)]
                result = sorted(result, key=itemgetter(1), reverse=True)
                
                print(f"Pontuação Final Acumulada -> Positivo: {pos:.2f} | Negativo: {neg:.2f}")
                return result[0][0]
        else:
            return ''
    except Exception as e:
        print(f"Erro: {e}")
        return ''

# Testando a nova implementação nativa em PT-BR!
texto_teste = "O Paulo é muito lindo e incrivelmente feliz"
print(f"Original: {texto_teste}\n" + "-"*40)

resultado = Polarity_PT(texto_teste)

print("-" * 40)
print(f"Sentimento predominante da frase: {resultado.upper()}")
