# pyrefly: ignore [missing-import]
import nltk
# pyrefly: ignore [missing-import]
from nltk.corpus import wordnet as wn

print(wn.synsets("poder",pos=wn.VERB,lang="por"))