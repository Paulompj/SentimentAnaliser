# Arquitetura do projeto

O projeto usa um **pacote Python organizado por camadas**. Todo o código da
aplicação fica em `analise_sentimentos/`; na raiz ficam apenas entradas de
comando, testes, documentação e os dados em `output/`.

```text
analiseSentimentos/
├── analise_sentimentos/
│   ├── domain/          # regras de período, candidatos e resumos
│   ├── sources/         # cliente e coletores do YouTube
│   ├── pipelines/       # WordNet e Transformers
│   ├── config/          # configurações da API e .env
│   └── web/             # HTML, CSS e JavaScript dos painéis
├── main.py              # entrada da análise WordNet de 2022
├── scripts/             # comandos operacionais, incluindo Transformer de 2026
├── tests/
├── docs/                # inclui experimentos antigos
└── output/              # bases e resultados; não foi movida
```

## Responsabilidades e dependências

`domain/` reúne regras que não dependem da API ou dos modelos. `sources/`
obtém os textos do YouTube. `pipelines/` orquestra a classificação e a
exportação, usando `domain/` e `sources/`.
`main.py` e `scripts/` são interfaces de linha de comando. `web/` contém os
arquivos servidos por `scripts/servir_painel.js`.

```text
main.py / scripts/
        │
        ▼
     pipelines/ ──────> sources/ ──────> YouTube
        │
        └──────> domain/
        │
        └──────> output/ (CSV, JSON e relatórios)
```

Dentro de `pipelines/`, os métodos são separados:

| Método | Arquivos | Entrada padrão | Saída padrão |
| --- | --- | --- | --- |
| WordNet/SentiWordNet | `wordnet.py`, `wordnet_model.py` | API ou CSV de comentários de 2022 | `output/` |
| Transformers, amostra | `transformer_chat.py`, `social_preprocessing.py`, `transformer_attribution.py` | amostra do chat de 2026 | `output/2026/` ou `output/2026/globo/` |
| Transformers, Band completa | `band_blocks.py` com os mesmos pré-processamento e modelo | cinco CSVs em `output/2026/blocos/` | `output/2026/bertweet_band/` |

O WordNet gera sentimento lexical geral, detalhes dos termos e avaliação com
rótulos humanos. O Transformer gera probabilidades para o sentimento do texto
inteiro; a regra de atribuição a candidato é uma aproximação separada.

## Executar

Na raiz do projeto, instale `requirements.txt` e os recursos do NLTK. O
Transformer também requer `requirements-modelo.txt`. Os comandos existentes
continuam válidos:

```powershell
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe scripts\classificar_chat_2026.py --help
.\.venv\Scripts\python.exe scripts\classificar_chat_globo.py --help
.\.venv\Scripts\python.exe scripts\classificar_blocos_band.py --help
node scripts\servir_painel.js
```

Para processar novamente um CSV de 2022 sem substituir os resultados atuais:

```powershell
.\.venv\Scripts\python.exe main.py --input-csv output\coleta.csv --output outra_pasta_de_resultados
```

## Bases existentes

Os comentários, análises e rótulos de 2022 continuam em `output/`. O chat,
os blocos e os rótulos de 2026 continuam em `output/2026/`; os dados da Globo
ficam em `output/2026/globo/`. Os dados atualmente versionados em `output/`
são incluídos no clone. O checkpoint SQLite e os caches de modelos são
ignorados pelo Git e precisam ser preparados novamente em outro ambiente.
