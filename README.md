# Análise de sentimento em debates presidenciais

O projeto usa um **pacote Python com organização por camadas** e dois métodos de
classificação independentes: WordNet/SentiWordNet para os comentários de 2022 e
Transformers para amostras do chat de 2026. `main.py` executa o fluxo WordNet;
os comandos em `scripts/classificar_chat_*.py` executam o fluxo Transformers.
Veja a [arquitetura](docs/ARQUITETURA.md) e o [fluxo detalhado de 2022](docs/FLUXO_DO_PROJETO.md).

## Organização das pastas

```text
analiseSentimentos/
├── analise_sentimentos/      # pacote da aplicação
│   ├── domain/              # períodos, candidatos e resumos
│   ├── sources/             # coleta via YouTube
│   ├── pipelines/           # WordNet e Transformers
│   ├── config/              # leitura do .env
│   └── web/                 # arquivos do painel local
├── main.py                  # comando WordNet
├── scripts/                 # comandos de coleta, classificação e utilitários
├── tests/                   # testes automatizados
├── docs/                    # guias, TCC, referências e experimentos antigos
└── output/                  # bases e resultados versionados
```

`.env` e `.venv/` permanecem na raiz. Os scripts em `docs/experimentos/` não são
importados por `main.py`; podem exigir dependências ou recursos próprios. Os
slides são material de apresentação e devem ser conferidos com o fluxo atual
antes de serem usados como descrição da metodologia.

As bases de comentários e rótulos permanecem em `output/` e `output/2026/`.
Os arquivos atualmente versionados são copiados ao clonar o repositório.
O checkpoint SQLite e os caches de modelos são ignorados pelo Git.

Este projeto investiga comentários relacionados ao debate do segundo turno
transmitido pela Band em 16/10/2022, desde as **20h até três horas após a
publicação do vídeo**. O início corresponde ao horário anunciado pela
[Band](https://www.band.com.br/politica/eleicoes/band-realiza-debate-entre-lula-pt-e-bolsonaro-pl-neste-domingo-16-16547955).
A API registra a publicação às **22h06min39s** de 16/10/2022; portanto, o fim
padrão é **01h06min39s de 17/10/2022**, no horário de Brasília (UTC-03).
O código calcula esse fim a partir de `snippet.publishedAt` retornado pela API.
No modo CSV, usa o horário de publicação já registrado para este vídeo.
O relatório separa comentários durante o debate daqueles publicados depois.

## Candidatos por edição

As regras em `analise_sentimentos/domain/targets.py` têm dois perfis: o padrão de **2022**
identifica Lula e **Jair Bolsonaro**; `detect_targets(texto,
election_year=2026)` identifica Lula e **Flávio Bolsonaro**. No perfil de 2026,
uma menção isolada a “Bolsonaro” é atribuída a Flávio pelo contexto do debate;
uma menção explícita a “Jair Bolsonaro” não é. Essa regra de sobrenome pode
errar em comentários que falem de familiares e deve ser revista na validação.

O restante de `main.py` ainda usa o vídeo, os horários, os nomes das colunas e
a pasta `output/` da análise de 2022. O perfil de menções de 2026, por si só,
não configura uma coleta nova nem altera os resultados de 2022.

## Instalação

No PowerShell, na pasta do projeto:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m nltk.downloader -d .venv\nltk_data stopwords wordnet sentiwordnet omw-2.0
```

Use Python 3.12 e Node.js 22 ou superior. Crie a `.venv` apenas na primeira
instalação. Configure
`YOUTUBE_API_KEY` em `.env`, usando `.env.example` como referência.

Para instalar também o classificador Transformers e os utilitários de PDF e
PowerPoint, registre o pacote em modo editável com os dois grupos opcionais:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[modelo,docs]"
```

As dependências dos utilitários também estão em `requirements-docs.txt`.
As 78 versões de dependências do ambiente validado no Windows com Python 3.12
estão registradas em `requirements-lock-windows-py312.txt`; esse snapshot é
específico dessa plataforma.
O painel usa apenas módulos nativos do Node.js e pode ser iniciado com
`npm start` ou `node scripts/servir_painel.js`. Não precisa de `npm install`.

Para validar o ambiente sem coletar dados ou substituir resultados:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_rotulacao_chat.js tests/test_web_routes.js tests/test_bertweet_dashboard.js
```

## Coleta e análise

### Painel BERTweet: termômetros, emojis e validação

Para conferir os resultados existentes da Band e preparar o painel:

```powershell
.\.venv\Scripts\python.exe scripts\validar_bertweet.py
node scripts\servir_painel.js
```

Abra **http://127.0.0.1:8765/resultados**. A tela mostra termômetros para
Lula e Flávio com suas fotos, contagens positivas e negativas nos termômetros,
filtros por bloco principal, Super Chats e presença de emojis, além de uma tabela
com busca, inspeção do texto preparado e exportação do recorte.

A posição do marcador compara mensagens positivas e negativas; o índice
numérico e os textos de predominância não são exibidos. O padrão
exclui os Super Chats; o bloco experimental não é oferecido no painel.
Os rótulos publicados são usados sem um novo filtro de probabilidade.
A polaridade da frase só é
associada a um candidato pela regra nominal conservadora existente. Essa
leitura não estima apoio, aprovação ou intenção de voto.
O endereço inicial `/` redireciona para `/resultados`, dedicado à Band de
2026. As telas da análise de 2022 e de rotulação não são servidas pelo painel.

**Emojis & ironia** apresenta frases construídas com o mesmo modelo,
o texto efetivamente recebido pelo tokenizer e suas subpalavras. A inspeção
explica a marca interna `@@` de continuação dos tokens BPE. As pistas de possível ironia são
heurísticas para revisão; não constituem um detector de ironia.

A auditoria separa a consistência técnica da acurácia ainda não medida com
rótulos humanos e é mantida nos arquivos, sem uma aba de validação na interface.
O comando confere todas as saídas e
reexecuta a amostra anterior mais uma amostra estratificada dos resultados.
Ele grava `auditoria.json` e `painel.json` em
`output/2026/bertweet_validacao/`, preservando os arquivos originais. O
servidor verifica os hashes de entrada e recusa uma auditoria desatualizada.
Depois de modificar as classificações ou preencher rótulos humanos, rode o
comando novamente. `--sem-inferencia` executa apenas a conferência dos
arquivos e deixa os experimentos do modelo vazios.

Veja os [resultados e limites da validação](docs/VALIDACAO_BERTWEET.md).

### Debate de 2026: chat ao vivo

O chat da transmissão e os comentários do vídeo publicado são fontes
diferentes. Para guardar as mensagens do **chat enquanto a live está ativa**,
inicie este comando na raiz do projeto, antes do debate:

```powershell
.\.venv\Scripts\python.exe scripts\coletar_chat_ao_vivo.py "LINK_DA_LIVE"
```

O programa aceita URL `watch`, `youtu.be`, `/live/` ou o ID de 11 caracteres.
Para acompanhar a execução pelo navegador, abra outro terminal e execute
`node scripts\servir_painel.js`; depois acesse `http://127.0.0.1:8765/coleta`.
Essa tela atualiza a cada três segundos e mostra a espera pela live, mensagens
salvas, páginas, último lote, horários, atividade recente, término e erros.
Se não houver atualização por mais de um minuto durante a coleta, ela avisa
para verificar o terminal. Também oferece o download do CSV já criado.

Durante a coleta, use **Iniciar bloco** e **Encerrar bloco atual** na mesma
tela para registrar os horários de cada etapa do debate em
`output/2026/blocos.json`. A captura do chat continua sem interrupção. Após
encerrar um bloco, o painel gera seu CSV separado e mostra um link para baixá-lo.
Para refazer a exportação após ajustar os horários em `blocos.json`, execute:

```powershell
.\.venv\Scripts\python.exe scripts\exportar_blocos_chat.py
```

Os arquivos ficam em `output/2026/blocos/`; o CSV bruto continua intacto.
Cada bloco usa o intervalo entre os cliques, aplicado ao `published_at` das
mensagens. Se um clique atrasar em relação à fala real do debate, confira os
horários antes da análise e ajuste `blocos.json` para corrigir o recorte.

Interrupções observadas na coleta ficam documentadas em
`output/2026/lacunas_coleta.json`. Um intervalo sem
registros não deve ser interpretado como ausência de mensagens no chat.

Ele espera o chat ficar ativo, consulta `liveChatMessages.list` usando o
`nextPageToken` e espera pelo menos o `pollingIntervalMillis` devolvido pela
API e três segundos entre requisições. Cada
resposta é adicionada imediatamente a `output/2026/chat_ao_vivo.csv`. O arquivo
`output/2026/chat_estado.json` guarda o próximo token, o total e se a coleta
terminou. Se a conexão ou o processo cair, execute o **mesmo comando** para
retomar; mensagens já salvas não serão duplicadas. O coletor termina quando a
API informa que a transmissão ficou offline ou que o chat encerrou. Não usa
uma hora fixa como corte, pois a duração real pode variar.

O CSV preserva `message_id`, horários de publicação e captura, tipo da
mensagem, texto e dados públicos do autor. Para analisar só o período do
debate, o recorte será aplicado a `published_at` depois de confirmar os horários
reais de início e fim. Mensagens anteriores ao primeiro acesso que não forem
incluídas na primeira resposta da API não poderão ser recuperadas por esse
método; por isso é importante iniciar cedo. O chat não pode ser buscado por
essa API depois que a live acaba.

O estado marca `coverage_verified=false`: o encerramento da coleta não prova
que todas as mensagens da audiência foram fornecidas pela API. A consulta de
chat consome 5 unidades de quota por chamada e, em um chat muito rápido, a
API pode limitar a quantidade entregue por página. A planilha preserva o
tipo da mensagem; a análise de opinião deverá selecionar `textMessageEvent`.

### Rotulação manual do chat de 2026

A tela de rotulação foi retirada da interface atual. O arquivo existente
`output/2026/rotulacao_chat_2026.csv` preserva 500 mensagens de texto distintas:
125 de cada bloco substantivo. O bloco experimental de sete segundos (`1 parte`)
fica fora da amostra. A seleção usa uma semente fixa e equilibra menções
aproximadas a Lula, Flávio, ambos e outras mensagens. A regra de seleção fica
em `output/2026/rotulacao_chat_2026_metadados.json`.

Para cada mensagem, escolha um rótulo para **Lula** e outro para **Flávio**:
`sem_referencia`, `positivo`, `negativo`, `neutro`, `misto` ou `incerto`.
`Sem referência` significa que a mensagem não avalia aquele candidato;
`neutro` significa que o cita sem avaliação; `incerto` significa que o texto
não permite decidir. Esses campos podem ser preenchidos diretamente no CSV,
preservando IDs, textos e demais metadados.

Essa amostra foi criada para construir e avaliar modelos. Como equilibra
blocos e menções, suas proporções não estimam a distribuição real de opiniões
no chat. Mensagens repetidas foram retiradas da amostra, mas continuam no CSV
bruto. A lacuna documentada durante o Bloco 2 permanece uma limitação dos dados.

### Classificação automática da amostra do chat de 2026

Se não houver tempo para rotular manualmente, instale as dependências opcionais
e execute o modelo já treinado para textos curtos em português:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-modelo.txt
.\.venv\Scripts\python.exe scripts\classificar_chat_2026.py
```

O resultado fica em `output/2026/rotulacao_automatica_chat_2026.csv`, com 500
linhas, rótulo geral (`positivo`, `negativo`, `neutro`), probabilidades por
classe, o texto preparado para o modelo e rótulos aproximados separados para
Lula e Flávio. O pré-processamento expande hashtags e emojis, normaliza
menções, URLs, risadas e letras repetidas; o texto original permanece ao lado.
Também pode ser
baixado em `http://127.0.0.1:8765/rotulacao-automatica.csv`, com o painel
local ligado. `rotulacao_automatica_chat_2026.json` guarda modelo, revisão,
versões, contagens e SHA-256 da amostra usada. O arquivo manual
`rotulacao_chat_2026.csv` não é alterado.

O classificador [`pysentimiento/bertweet-pt-sentiment`](https://huggingface.co/pysentimiento/bertweet-pt-sentiment)
prevê **sentimento do texto inteiro**, não apoio a candidatos. O script só
associa essa polaridade a um candidato quando o nome dele é a única referência
identificável e a maior probabilidade do modelo chega a 0,60. Se aparecem os
dois, somente `13`, somente `22`, o sobrenome `Bolsonaro` isolado ou uma
probabilidade baixa, o rótulo dirigido fica `incerto`. `sem_referencia` quer
dizer que não foi encontrada uma menção identificável. O campo
`regra_atribuicao` mostra a razão. Gritos de torcida, ironia, emojis e críticas
a outros assuntos podem gerar erros mesmo com probabilidade alta.
Na conferência inicial, por exemplo, "Bora Lula" apareceu como `neutro`:
o classificador de polaridade pode não reconhecer um grito de apoio como apoio
político. Não interprete a coluna `neutro` como ausência comprovada de apoio.

Esses rótulos são **previsões automáticas**, não uma base verdadeira para treino
e teste. Treinar outro modelo neles e depois compará-lo com os mesmos rótulos
mediria concordância com o primeiro modelo, não acurácia. As probabilidades
também não são taxa de acerto. A estratificação da amostra impede usar suas
proporções como prevalência do chat inteiro.

### Classificação dos blocos completos da Band

Para classificar as mensagens capturadas nos cinco CSVs de
`output/2026/blocos/`, execute:

```powershell
.\.venv\Scripts\python.exe scripts\preparar_modelo.py
.\.venv\Scripts\python.exe scripts\classificar_blocos_band.py
```

Execute `preparar_modelo.py` uma vez por ambiente para baixar e verificar a
revisão fixada no cache `.cache_huggingface/` (cerca de 540 MB). O classificador
dos blocos usa somente o cache local; instalar `torch` e `transformers` não
baixa os pesos do modelo.

O comando usa a revisão do BERTweet já aplicada à amostra de 500 mensagens e
confere se suas previsões continuam equivalentes antes de avançar. Classifica
mensagens `textMessageEvent` e, separadamente, o comentário extraído de
`superChatEvent` quando o texto é identificável. Stickers e Super Chats sem
comentário extraível ficam em `nao_classificados.csv`. Textos repetidos são
inferidos uma vez, mas cada `message_id` permanece no resultado. A execução
pode ser retomada pelo `checkpoint.sqlite` após uma interrupção.

Os novos arquivos ficam em `output/2026/bertweet_band/`:
`classificacao.csv` para mensagens comuns, `superchats_classificados.csv`,
`nao_classificados.csv`, `resumo_blocos.csv` e `execucao.json` com modelo,
versões, hashes das fontes, conferência da amostra e totais. O bloco curto
`1 parte` aparece separado dos quatro blocos principais. O resumo documenta
a lacuna de coleta que atravessa o Bloco 2. O comando não modifica os CSVs
originais nem o arquivo de rótulos humanos.

As proporções são descrições das **mensagens capturadas**. O modelo prevê
sentimento geral; as colunas por candidato são aproximações exploratórias e
não medem apoio ou oposição. A comparação com as 500 previsões antigas
verifica consistência do processamento, não acurácia.
Veja o [resumo da execução completa](docs/RESULTADOS_BERTWEET_BAND.md).

Depois da publicação do vídeo, a coleta de **comentários do vídeo** usará
`commentThreads.list`, com o link/ID da versão publicada e uma janela separada:
da publicação até três horas depois. Ela será salva em outro CSV dentro de
`output/2026/`. A data `snippet.publishedAt` de uma live agendada pode não
representar o momento em que o arquivo ficou público após o debate; esse
horário deverá ser conferido antes de fixar o recorte. Depois que as três
horas terminarem, execute:

```powershell
.\.venv\Scripts\python.exe scripts\coletar_comentarios_2026.py "LINK_DO_VIDEO_PUBLICADO"
```

Se o vídeo publicado for o mesmo ID da live e `snippet.publishedAt` for
anterior ao fim da transmissão, o programa exigirá o horário real de
disponibilização da versão publicada:

```powershell
.\.venv\Scripts\python.exe scripts\coletar_comentarios_2026.py "LINK_DO_VIDEO_PUBLICADO" --published-at "2026-10-18T22:00:00-03:00"
```

O horário acima é apenas um exemplo; use o horário observado. O resultado
ficará em `output/2026/comentarios_pos_publicacao.csv`, com metadados da janela
em `comentarios_pos_publicacao_resumo.json`. Os dois CSVs têm fontes distintas
e não são misturados com `output/` de 2022. Esta etapa coleta os textos, sem
classificá-los; a análise por candidato exigirá usar o perfil de 2026.

### Debate de 2022: comentários do vídeo

```powershell
.\.venv\Scripts\python.exe main.py
```

O programa percorre as páginas de `commentThreads.list` em ordem temporal
até alcançar o início da janela. Seleciona comentários principais com
`publishedAt` entre o início e três horas após a publicação do vídeo, incluindo
os limites. Comentários editados após o fim do recorte também são excluídos,
pois o texto atual pode diferir do texto original.
A coleta é deduplicada por ID. Uma falha da API encerra o processo sem gerar
um relatório parcial como se fosse completo.

Arquivos gerados em `output/`:

| Arquivo | Conteúdo |
| --- | --- |
| `coleta.csv` | ID, texto, datas, período, curtidas e número de respostas dos comentários elegíveis |
| `analise.csv` | Período, sentimento geral automático, escores, menções explícitas e posição ainda não avaliada |
| `analise_detalhada.jsonl` | Um registro por comentário com texto, classificação, escores totais, termos e synsets |
| `synsets.csv` | Uma linha por termo e synset, para filtrar pelo `comment_id` em uma planilha |
| `sentimento_por_mencao.csv` | Contagens de sentimento geral em comentários que mencionam cada candidato e em grupos exclusivos |
| `relatorio_por_mencao.md` | A mesma tabela, com aviso sobre sobreposição e interpretação |
| `rotulacao.csv` | Amostra para rotulagem humana; criada uma vez para preservar trabalho preenchido |
| `rotulacao_b.csv` | Subamostra de 25% para uma segunda pessoa rotular sem ver os rótulos da primeira |
| `resumo.json` | Janela, metadados do vídeo, cobertura e contagens |
| `relatorio.md` | Resultados e limitações declaradas |
| `avaliacao.json` | Fica pendente após `run`; recebe métricas quando `evaluate` é executado com rótulos humanos |

Para um diagnóstico curto da coleta, `--max-pages 2` limita as páginas. O
relatório indicará **coleta incompleta**, e esses resultados não devem ser
tratados como a população do período.

Depois da última página da API, o programa analisa os textos. Agora ele mostra
o progresso a cada 500 comentários; essa etapa pode levar alguns minutos.
Para gerar os detalhes a partir de um `analise.csv` já existente, sem nova
consulta à API, execute:

```powershell
.\.venv\Scripts\python.exe main.py details
.\.venv\Scripts\python.exe scripts\inspecionar_analise.py --numero 1
```

No segundo comando, substitua `--numero 1` por `--id IDENTIFICADOR` para
consultar um comentário específico. O ID está em `analise.csv`. Em
`synsets.csv`, `pos_score_synset`, `neg_score_synset` e `obj_score_synset` são
os escores originais de cada synset; `pos_score_token` e `neg_score_token` são
a média dos synsets do termo, após a regra de negação. A soma das contribuições
dos termos forma os escores totais em `analise.csv`. Termos sem synset com
escore lexical aparecem sem synset e contribuem com zero. Não some diretamente
as linhas de `synsets.csv`: a contribuição de um termo se repete em cada linha
dos seus synsets.

### Interface atual

O servidor local apresenta os resultados BERTweet da Band de 2026 em
`http://127.0.0.1:8765/resultados`. O endereço inicial redireciona para essa
tela. A interface histórica de 2022 e a tela de rotulação foram retiradas do
servidor; arquivos e ferramentas de pesquisa anteriores permanecem no
repositório para consulta. O servidor usa apenas módulos internos do Node.js.

### Fonte externa de chat

`commentThreads.list` obtém comentários do vídeo, não mensagens do chat ao
vivo. Se houver uma exportação autorizada do chat da transmissão, ela pode
ser importada como CSV com pelo menos `comment_id`, `text` e `published_at`
(ISO 8601 com fuso):

```powershell
.\.venv\Scripts\python.exe main.py --input-csv chat.csv
```

`updated_at`, `like_count` e `reply_count` são opcionais. O mesmo recorte
temporal é aplicado. A cobertura de um arquivo externo não é presumida como
completa; o relatório registra essa condição. Não misture chat e comentários
do vídeo na mesma inferência sem identificar as duas fontes.

## O que a classificação mede

`pt_core_news_lg` identifica lemas e classes gramaticais. O SentiWordNet
atribui escores léxicos; o programa usa a média dos sentidos encontrados e
uma regra local de negação para formar uma **linha de base de sentimento
geral**. Diferenças relativas de até 10% entre os escores são chamadas de
`neutral`; ausência de escore vira `insufficient_evidence`. Esses parâmetros
são heurísticos e ainda precisam ser validados com rótulos humanos.

A detecção de Lula e Bolsonaro encontra nomes, alguns apelidos e os números
eleitorais como termos inteiros. Um comentário pode mencionar os dois ou
nenhum. Menção não é apoio. As colunas `stance_lula` e
`stance_bolsonaro` permanecem `nao_avaliada` até ser desenvolvido e validado
um classificador específico de posição política.

### Contagens por candidato mencionado

Para gerar a tabela a partir de `analise.csv`, sem nova coleta, execute:

```powershell
.\.venv\Scripts\python.exe main.py candidates
```

Abra `output/relatorio_por_mencao.md` ou `output/sentimento_por_mencao.csv`.
`menciona_lula` e `menciona_bolsonaro` incluem comentários que citam ambos;
por isso, essas linhas se sobrepõem. As linhas `somente_lula`,
`somente_bolsonaro`, `ambos` e `nenhum` não se sobrepõem. Os rótulos `positive`
e `negative` descrevem o **comentário inteiro**, não aprovação ou rejeição ao
candidato. Para medir apoio e oposição, use as colunas de posição da rotulagem
humana e valide um método específico para essa tarefa.

Para gerar duas pizzas com as quatro classes de sentimento a partir dessa tabela:

```powershell
.\.venv\Scripts\python.exe scripts\gerar_grafico_pizza.py
```

Os arquivos `output/grafico_pizza_sentimento_por_mencao.png` e `.pdf` são
gerados sem nova chamada à API. Os percentuais usam o total de cada grupo;
comentários que mencionam ambos aparecem nas duas pizzas.

## Rotulagem e avaliação

### Piloto de 10 comentários: sentimento dirigido ao candidato

Abra `output/rotulacao_por_candidato_piloto_10.csv`. Ele já contém os 10
primeiros comentários da amostra, sem rótulos preenchidos. Em cada linha,
preencha a coluna **D** (`candidato`) com `lula` ou `bolsonaro` e a coluna **E**
(`sentimento`) com `positivo`, `negativo`, `neutro`, `misto` ou `incerto`.
Use `nenhum` em `candidato` e deixe `sentimento` vazio
quando o texto não se referir claramente a nenhum dos dois. Não altere
`numero`, `comment_id` ou `text`.

O sentimento deve se referir **ao candidato daquela linha**. `positivo` indica
elogio ou avaliação favorável; `negativo`, crítica; `neutro`, menção sem
avaliação; `misto`, avaliações favoráveis e desfavoráveis sobre o mesmo
candidato; `incerto`, referência identificável com tom indeterminado.
Para “O Lula não presta”, marque `lula` e `negativo`. Se um comentário avaliar
os dois candidatos, copie a linha com o mesmo `comment_id` e preencha uma linha
para cada candidato. Por exemplo, “Lula foi ótimo; Bolsonaro foi péssimo” gera
uma linha `lula,positivo` e outra `bolsonaro,negativo`. Sentimento favorável
não é necessariamente intenção de voto ou apoio político.

Esse piloto registra os **rótulos humanos** por candidato. O programa atual
classifica o sentimento do comentário inteiro e só detecta menções aos nomes;
ainda não prevê sentimento separado para Lula e Bolsonaro. Portanto, não há
porcentagem de acerto por candidato a calcular agora. Depois de definir os
critérios com o piloto, será necessário criar essa previsão por candidato e
compará-la aos rótulos das mesmas linhas. As pizzas por menção também não
representam aprovação ou rejeição a cada candidato.

### Avaliação do sentimento geral existente

Para avaliar a classificação **do comentário inteiro**, abra
`output/rotulacao.csv` e preencha `sentimento_geral` (coluna **E**) nas linhas
2 a 11 para começar com 10 comentários. Use `positive`, `negative`, `neutral`
ou `insufficient_evidence`. Leia o texto antes de consultar a previsão em
`output/analise.csv`. Mantenha `comment_id`, datas e textos intactos. As colunas
`posicao_lula` e `posicao_bolsonaro` servem para posição política explícita e
podem ficar vazias no piloto. Uma segunda pessoa pode rotular depois a amostra
separada em `output/rotulacao_b.csv` para medir concordância.

Execute:

```powershell
.\.venv\Scripts\python.exe main.py evaluate
```

`output/avaliacao.json` terá matriz de confusão, precisão, revocação e F1
por classe para sentimento geral e detecção de menções, quando houver rótulos
preenchidos. Também mostrará a concordância observada e o kappa de Cohen
entre as duas pessoas, além da distribuição dos rótulos humanos de posição.
O campo `sentiment.accuracy_percent` é a porcentagem de comentários rotulados
cujo sentimento previsto coincide exatamente com o rótulo humano:
`sentiment.correct / sentiment.n × 100`. As quatro classes entram no cálculo,
inclusive `insufficient_evidence`. `sentiment.n` conta apenas linhas com rótulo
válido; depois de preencher as primeiras 10, deve valer 10. A matriz de
confusão e o F1 por classe mostram erros que a porcentagem geral pode esconder.
Como a amostra foi balanceada por tipo de menção a candidato, a porcentagem
descreve a amostra rotulada; não representa automaticamente os 15.088
comentários. O programa ainda não calcula desempenho de posição política.

## Limitações importantes para o TCC

- A transmissão acabou às 21h52min18s e o vídeo foi publicado às 22h06min39s.
  Os comentários comuns feitos após 21h52min18s descrevem **repercussão após
  a transmissão**, não reação publicada durante o debate. Os períodos aparecem
  separados nos CSVs, no resumo e no relatório.
- Há comentários datados antes do `publishedAt` do vídeo. Esse horário serve
  como marco para as três horas, mas não indica quando a página da transmissão
  passou a aceitar comentários.
- As 20h são o início anunciado pela Band, usado como referência operacional;
  a hora exata da primeira fala do debate não foi verificada minuto a minuto.
- O [chat ao vivo](https://developers.google.com/youtube/data/live/reference/rest/v3/liveChatMessages)
  é um recurso separado. A API oficial informa que ele deixa de estar
  disponível após a transmissão. Um arquivo histórico só pode ser analisado
  se houver um replay ou exportação acessível e verificável. Na verificação
  deste vídeo em 18/10/2026, o replay do chat não apareceu entre os dados
  disponíveis para extração; isso não prova que nenhuma cópia exista fora
  das fontes consultadas.
- A coleta atual cobre comentários principais ainda públicos na data da
  coleta; respostas, exclusões e mensagens removidas ficam fora.
- Regras léxicas não resolvem bem ironia, gírias, contexto e referências
  indiretas. O modelo LG não foi treinado para sentimento ou posição política.
- Os comentários observados não representam todos os espectadores nem a
  população eleitoral. O relatório descreve o conjunto acessível na fonte
  e no período, com as respectivas limitações.
