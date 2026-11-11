# Análise técnica do projeto

Análise realizada em 11/11/2026 no Windows, incluindo código da aplicação,
scripts, testes, configuração, painéis, documentação e consistência das bases
existentes. Os PDFs e slides de referência foram inventariados; esta análise
não é uma revisão acadêmica integral de seu conteúdo.

## Estrutura e funcionamento

O pacote está separado em domínio (`domain`), fontes do YouTube (`sources`),
pipelines de classificação (`pipelines`), configuração (`config`) e interface
local (`web`). Os scripts operacionais delegam a maior parte do trabalho ao
pacote. O servidor Node.js usa somente módulos nativos e escuta em
`127.0.0.1`, na porta 8765 por padrão.

| Fluxo | Responsabilidade | Dependências principais |
| --- | --- | --- |
| WordNet, 2022 | Coletar/importar comentários, calcular escores léxicos, exportar detalhes e avaliar rótulos humanos | requests, dotenv, truststore, spaCy, pt_core_news_lg, NLTK e corpora |
| Transformers, 2026 | Classificar sentimento geral e aplicar regras exploratórias de atribuição por candidato | torch, transformers, emoji e pesos BERTweet |
| Band completa | Validar cinco blocos, conferir a amostra anterior, reutilizar previsões e persistir checkpoint | Mesmo modelo Transformers e SQLite da biblioteca padrão |
| Painéis | Explorar análise, monitorar coleta e registrar rótulos humanos | Node.js; sem pacotes npm externos |
| Utilitários | Gerar gráficos e apresentações e extrair texto de PDFs | matplotlib, python-pptx e PyPDF2 |

Pontos positivos: separação entre polaridade e apoio político; preservação do
texto original; deduplicação por ID; persistência incremental do chat;
gravações temporárias em vários fluxos; hashes e revisão fixa no processamento
da Band; detecção de conflitos entre abas na rotulação; uso de `textContent`
para mostrar os comentários no navegador.

## Ajustes de instalação e documentação

- Criado ambiente Python 3.12 em `.venv` e instalado Node.js LTS.
- Declaradas as dependências do pacote no `pyproject.toml`, reutilizando os
  arquivos de requisitos, com extras `modelo` e `docs`.
- Registradas 78 versões de dependências do ambiente instalado em
  `requirements-lock-windows-py312.txt`, específico do Windows/Python 3.12.
- Criado `requirements-docs.txt` para `python-pptx` e `PyPDF2`, anteriormente
  importados pelos utilitários sem declaração de instalação.
- Criado `package.json` com `npm start` e `npm test`, sem dependências externas.
- Criado `scripts/preparar_modelo.py` para baixar e validar a revisão BERTweet
  necessária ao classificador da Band, que trabalha apenas com cache local.
- Instalados o modelo spaCy `pt_core_news_lg` 3.8.0 e os recursos NLTK
  `stopwords`, `wordnet`, `sentiwordnet`, `omw-2.0`, `omw-1.4`, `mac_morpho`
  e `punkt_tab` em `.venv/nltk_data`, incluindo os usados pelos protótipos.
- Atualizadas as instruções no README e a informação sobre os dados no Git.
  Há 34 arquivos versionados em `output/`; apenas o checkpoint indicado e os
  caches estão ignorados. As bases existentes foram preservadas.
- Criado `.env` local com `YOUTUBE_API_KEY` vazia. A chave real ainda precisa
  ser preenchida para novas coletas.

## Conferência das bases existentes

| Verificação | Resultado |
| --- | --- |
| Comentários de 2022 | 15.088 elegíveis, de 33.153 examinados, conforme resumo existente |
| CSV e JSONL de 2022 | 15.088 registros conciliados, sem divergências de rótulo, escores ou soma dos termos |
| Amostras humanas de 2022 | 500 e 125 linhas; nenhuma com sentimento geral preenchido |
| Cinco blocos da Band | 24.522 registros de entrada |
| Mensagens comuns classificadas | 23.594 |
| Super Chats classificados | 649 |
| Registros excluídos | 279 |
| IDs nos três arquivos de saída da Band | 24.522 distintos e sem sobreposição |
| SHA-256 dos cinco CSVs de origem | Todos coincidem com `execucao.json` |
| SHA-256 da amostra de 500 mensagens | Coincide com os metadados das previsões anteriores |
| Rótulos humanos da Band | 500 linhas; nenhuma anotada |

O hash do código de pré-processamento difere do histórico por causa da
conversão automática de LF para CRLF neste checkout (`core.autocrlf=true`).
Normalizar o arquivo para LF reproduz exatamente o SHA-256 registrado.
Portanto, essa divergência de bytes não indica mudança nas regras do modelo.
Ela mostra que hashes de código e fingerprints precisam de uma política de
finais de linha estável, por exemplo com `.gitattributes`.

## Pendências e melhorias por prioridade

1. **Validação científica:** não há rótulos humanos preenchidos para estimar
   acurácia. As 500 previsões antigas são uma referência de regressão do
   processamento, não verdade de referência. Os rótulos humanos da interface
   de 2026 são por candidato; avaliar sentimento geral do BERTweet exige
   também rótulos humanos da mesma tarefa e um procedimento de avaliação.
2. **Reprodutibilidade:** o fluxo da Band fixa a revisão do modelo, mas
   `transformer_chat.py` baixa a revisão padrão vigente e apenas a registra
   depois. Convém fixar a revisão também nesse fluxo. As versões das
   dependências do ambiente instalado foram registradas no arquivo de lock.
3. **Globo ainda sem dados:** a pasta contém somente um `blocos.json` com
   horários `PREENCHER`. Coleta, recorte e classificação dependem de dados e
   horários reais. O painel está fixado nos caminhos da Band; não acompanha
   automaticamente uma coleta na subpasta da Globo.
4. **Amostragem da Globo:** `exportar_blocos_chat_globo.py` inclui o grupo
   `fora_de_bloco`, não elimina IDs/textos repetidos e substitui a amostra
   existente. Antes de usá-lo em uma base anotada, definir as regras de
   exclusão, deduplicação e preservação das anotações.
5. **Configuração de experimentos:** o fluxo Band exige exatamente cinco
   blocos e uma referência anterior de 500 mensagens. Mesmo com `--entrada`,
   a amostra de conferência continua vinculada à pasta padrão da Band.
   Generalizar esses parâmetros antes de reutilizá-lo em outros debates.
6. **Manutenção:** os coletores de comentários e as entradas de chat para
   Band/Globo têm código duplicado. `sources/client.py` é um cliente antigo,
   sem a mesma política de erros do coletor atual. Unificar os comandos e
   remover ou sinalizar o legado reduziria divergências futuras.
7. **Inicialização WordNet:** `spacy.load` acontece durante a importação do
   módulo. Até `main.py --help`, `evaluate` e `candidates` exigem o modelo
   linguístico completo. Carregamento sob demanda deixaria esses comandos
   mais leves e permitiria erros de instalação mais claros.
8. **Manuscrito LaTeX:** faltam `image.png`, quatro imagens em `figures/` e
   `Referencias.bib`. Instalar um compilador não resolve esses arquivos
   ausentes. O texto também descreve tokenização NLTK e soma de synsets,
   enquanto o código atual usa tokenização spaCy e médias por termo; revisar
   a metodologia escrita antes de apresentar resultados.
9. **Cobertura automatizada:** os testes existentes exercitam regras,
   persistência e algumas rotas, mas não substituem testes de erro/quota da
   API, avaliação humana e conferência visual dos painéis. Não há workflow
   de CI no checkout analisado.

## Execução

Na raiz do projeto, use o Python da `.venv`:

```powershell
.\.venv\Scripts\python.exe main.py --help
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test tests/test_rotulacao_chat.js tests/test_web_routes.js
node scripts\servir_painel.js
```

Depois abra `http://127.0.0.1:8765`. Novas coletas do YouTube requerem a chave
no `.env`. Depois da instalação de Python/Node.js, abra um terminal novo para
que os comandos adicionados ao PATH fiquem disponíveis.

## Validações realizadas

- 28 testes Python aprovados em `unittest discover -s tests -v`.
- 3 testes Node.js aprovados, incluindo inicialização do servidor e acesso às
  páginas `/`, `/coleta`, `/rotulacao` e ao JavaScript do painel.
- `pip check`: nenhuma dependência incompatível ou ausente.
- Instalação editável com os extras `modelo` e `docs` concluída.
- `main.py --help` e `classificar_blocos_band.py --help` executados.
- Sintaxe dos 46 arquivos Python e dos scripts principais do navegador
  conferida; referências literais a IDs do DOM encontradas nos três HTMLs.
- Dependências dos utilitários importadas; apresentação existente com 7
  slides e PDF do TCC com 43 páginas abertos sem regravar os arquivos.
- BERTweet e tokenizer preparados no cache local na revisão
  `726612815d49447cbfe3f55bbfc2993c1f5fad10`.
- Nova inferência das 500 mensagens da amostra conferida com
  `verify_existing_sample`: todos os rótulos e regras de atribuição
  equivalentes à referência; maior diferença de probabilidade
  `0,0000011028785705802235`, dentro da tolerância do projeto.
- Os SHA-256 dos 34 arquivos de `output/` permaneceram idênticos após as
  verificações. A inferência de conferência usou um checkpoint temporário.

Ambiente principal validado: Python 3.12.10, Node.js 26.13.0, spaCy 3.8.18,
NLTK 3.10.4, Torch 2.14.1, Transformers 4.57.6 e emoji 2.16.0.
