# Classificação BERTweet do chat da Band de 2026

Execução concluída em 10/11/2026 com o modelo
[`pysentimiento/bertweet-pt-sentiment`](https://huggingface.co/pysentimiento/bertweet-pt-sentiment),
revisão `726612815d49447cbfe3f55bbfc2993c1f5fad10`.

## Cobertura

Os cinco CSVs em `output/2026/blocos/` contêm **24.522 registros** e **24.522
IDs distintos**. O resultado reconcilia todos eles:

| Categoria | Registros | Arquivo de resultado |
| --- | ---: | --- |
| Mensagens comuns de texto | 23.594 | `output/2026/bertweet_band/classificacao.csv` |
| Super Chats com comentário extraível | 649 | `output/2026/bertweet_band/superchats_classificados.csv` |
| Super Chats sem comentário extraível e stickers | 279 | `output/2026/bertweet_band/nao_classificados.csv` |

Foram inferidos **17.442 textos distintos**. Repetições exatas receberam a
mesma previsão, e cada mensagem permaneceu como linha individual no CSV. O
bloco experimental `1 parte` está presente nos resultados, mas separado da
síntese dos quatro blocos principais.

## Sentimento geral das mensagens comuns

| Bloco | Mensagens | Positivo | Neutro | Negativo |
| --- | ---: | ---: | ---: | ---: |
| Bloco 1 - Livre | 10.789 | 1.726 | 5.171 | 3.892 |
| Bloco 2 | 4.193 | 671 | 2.081 | 1.441 |
| Bloco 3 | 6.298 | 937 | 3.342 | 2.019 |
| consideracoes | 2.197 | 401 | 1.089 | 707 |
| **Quatro blocos principais** | **23.477** | **3.735 (15,91%)** | **11.683 (49,76%)** | **8.059 (34,33%)** |
| 1 parte, experimental | 117 | 38 | 52 | 27 |

Os Super Chats classificados têm uma distribuição própria em
`resumo_blocos.csv`; não entram nas proporções da tabela acima. O relatório
`execucao.json` guarda hashes dos arquivos de origem, versões das bibliotecas,
parâmetros, contagens por bloco e a revisão do modelo. Quatro mensagens
classificadas ultrapassaram o limite de 128 tokens e foram truncadas.

## Verificação e interpretação

Antes da classificação completa, o pipeline comparou **500 previsões
automáticas antigas** em `output/2026/rotulacao_automatica_chat_2026.csv`.
Todos os rótulos coincidiram; a maior diferença entre probabilidades foi
`0,00000055`. Essa comparação verifica a consistência do novo comando com o
anterior. O arquivo de rotulação humana da amostra tem os campos de rótulo
vazios, então **não existe estimativa de acurácia**.

O modelo atribui polaridade ao **texto inteiro**. As colunas aproximadas para
Lula e Flávio não medem apoio, voto ou oposição. A amostra do chat foi
estratificada, e esta base completa contém apenas mensagens capturadas pela
API. Há uma [lacuna de coleta](../output/2026/lacunas_coleta.json) de cerca de
9 minutos e 38 segundos que atravessa o fim do Bloco 2; ausência de registros
nesse intervalo não significa ausência de mensagens.

As bases de origem, a amostra manual e as 500 previsões anteriores ficaram
inalteradas: seus hashes SHA-256 foram conferidos antes e depois da execução.
