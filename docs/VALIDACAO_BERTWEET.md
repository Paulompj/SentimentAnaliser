# Validação dos resultados BERTweet e painel

Conferência realizada em 11/11/2026. Painel local em
`http://127.0.0.1:8765/resultados`, servido por `scripts/servir_painel.js`.
O painel apresenta apenas as abas Termômetro e Emojis & ironia. A auditoria
e os testes de remoção de emojis continuam documentados nos arquivos, sem
seções correspondentes na interface.

## Resultado da auditoria

As 24.243 previsões classificadas passaram na conferência de probabilidades,
soma das classes, escolha do rótulo de maior probabilidade, confiança,
pré-processamento, atribuição por candidato, versão do modelo e indicação de
truncamento. Os 24.522 IDs de entrada foram conciliados: 23.594 mensagens
comuns, 649 Super Chats com comentário e 279 exclusões, sem duplicatas ou
sobreposição entre as três saídas. Textos e metadados conferem com as fontes,
assim como os hashes dos cinco CSVs e os resumos por bloco.

Foi executada nova inferência de 500 mensagens da referência anterior e 174
mensagens selecionadas dos resultados atuais, incluindo exemplos com emoji,
pistas para revisão de ironia, seleção geral e todos os truncados. Esses
grupos podem se sobrepor. Não houve divergências de rótulos nem de contagens
de tokens; a maior diferença de probabilidade foi aproximadamente
`0,0000010433`, abaixo da tolerância `0,0001`. Foram inferidos 772 textos
distintos no total, contando os testes diagnósticos e as versões sem emoji.

Isso valida consistência e reprodução de uma amostra. **Não demonstra que
as interpretações semânticas estejam corretas**. As 500 mensagens da amostra
humana continuam sem anotações. Não há acurácia mensurada no chat, nem um
classificador validado de apoio político ou ironia neste pipeline.

## Termômetro por candidato

Recorte padrão: quatro blocos principais, 23.477 mensagens comuns,
probabilidade mínima de 60%, sem Super Chats nem bloco experimental.

| Candidato | Positivas | Negativas | Neutras | Incertas | Referências detectadas | Índice |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lula | 1.163 | 1.637 | 1.692 | 2.568 | 7.060 | −16,9 |
| Flávio Bolsonaro | 301 | 2.242 | 1.508 | 3.655 | 7.706 | −76,3 |

O índice é `100 × (positivas − negativas) / (positivas + negativas)`.
Na interface, os termômetros exibem apenas positivas e negativas, com fotos
dos candidatos. O bloco experimental não aparece no seletor nem entra nos
recortes. A interface usa os rótulos publicados, sem filtro adicional de
probabilidade e sem opção de excluir pistas de ironia.
O índice numérico e os rótulos de predominância não são mostrados nos cartões;
o cálculo serve apenas à posição do marcador. A entrada principal abre os
resultados da Band de 2026; as telas de 2022 e rotulação não são expostas.
Neutras e incertas não entram nesse denominador. As referências detectadas
incluem casos ambíguos e se sobrepõem quando há referências aos dois.
“Sem referência” significa ausência de uma referência identificada pelas
regras, não prova de ausência de um alvo implícito.

O modelo prevê polaridade da frase inteira. A regra do projeto só transporta
essa polaridade para uma menção nominal única e com probabilidade suficiente.
Mesmo assim, “Lula chegou e a transmissão está horrível” pode transferir uma
crítica à transmissão para Lula. Nomes não resolvem o alvo semântico.
Portanto, os valores da tabela são **aproximações exploratórias**, não índices
de aprovação, votos ou quantidades comprovadas de elogios/críticas dirigidos
ao candidato. Repetições contam como mensagens individuais, e a lacuna de
coleta de cerca de 9min38s limita a cobertura.

## Emojis: o caminho real neste projeto

O programa chama `preprocess_social_text`, que usa `emoji.demojize` em
português. Em seguida, Transformers tokeniza essa entrada e executa o modelo
com no máximo 128 tokens, incluindo os marcadores especiais. No tokenizer
carregado do cache, `normalization=false`; portanto, a transformação de
emoji vem do código do projeto antes da tokenização.

Exemplos efetivamente produzidos:

| Original | Entrada do modelo |
| --- | --- |
| `👏` | `emoji mãos aplaudindo emoji` |
| `❤️` | `emoji coração vermelho emoji` |
| `🙄` | `emoji rosto com olhos revirados emoji` |
| `🤮` | `emoji rosto vomitando emoji` |
| `🇧🇷` | `emoji bandeira brasil emoji` |
| `2️⃣2️⃣` | `emoji tecla 2 emoji emoji tecla 2 emoji` |
| `kkkkkkkk` | `kk` |

Esses rótulos linguísticos não determinam a intenção do emoji no comentário.
Uma bandeira pode ser apoio, identidade ou decoração; 🙄 pode modificar o
tom da frase sem o classificador conseguir interpretá-lo corretamente.

No teste pareado de 60 mensagens reais com emoji, remover os emojis mudou o
rótulo de **22 mensagens (36,7%)**. Foi usada seleção aleatória com semente
fixa, não uma amostra desenhada para estimar o efeito em todo o chat. Esse
teste mede sensibilidade da previsão à remoção, não acurácia, causalidade
linguística ou qual das duas versões está correta. Remover emojis pode deixar
a entrada vazia quando a mensagem só contém símbolos.

## Ironia: exemplos de limitações observadas

Frases construídas e inferidas na mesma revisão do modelo:

| Frase | Classe prevista | Maior probabilidade |
| --- | --- | ---: |
| Lula foi muito bem. | positivo | 73,77% |
| Lula foi muito bem 👏 | positivo | 98,93% |
| Lula foi muito bem 🙄 | positivo | 80,35% |
| Lula foi muito bem, só que não. | neutro | 58,61% |
| Lula é um gênio: só fala besteira 🙄 | negativo | 98,01% |
| Flávio foi muito bem 🙄 | positivo | 77,81% |
| Flávio foi muito bem, só que não. | negativo | 47,64% |
| Lula falou no debate 🤮 | neutro | 80,31% |

A contradição explícita “só que não” foi construída para negar o elogio.
O rótulo neutro no exemplo de Lula é um contraexemplo à ideia de que o modelo
resolve essa construção de forma confiável. O mesmo molde com Flávio recebe
classe diferente e baixa probabilidade. Já 🙄 mantém o elogio como positivo
nos dois exemplos, apesar de ser uma pista possível de sarcasmo. Não é
possível decidir a intenção de qualquer uso real de 🙄 apenas pelo símbolo.

**O classificador carregado tem apenas NEG, NEU e POS.** Ele pode aprender
algumas combinações contextuais, mas o pipeline não pede nem produz uma
decisão de ironia. Transformers é a biblioteca que executa tokenizer e rede;
ela não adiciona automaticamente uma capacidade de detectar sarcasmo.

O painel apenas sinaliza `sqn`, “só que não”, “aham”, “confia”, 🙄 e 🤡 como
pistas para inspeção. Essas regras não detectam toda ironia e podem marcar
textos não irônicos. Excluí-las não produz uma base comprovadamente sem
ironia. O pysentimiento disponibiliza ironia como tarefa e modelo separados;
não foi instalado um segundo detector nem alteradas as previsões originais.

## Como reproduzir

```powershell
.\.venv\Scripts\python.exe scripts\preparar_modelo.py
.\.venv\Scripts\python.exe scripts\validar_bertweet.py
node scripts\servir_painel.js
```

A auditoria JSON registra revisão, versões, amostragem, hashes e tolerância.
O painel bloqueia o uso se os arquivos de entrada mudarem. Para atualizar a
auditoria após novas classificações ou anotações, execute o validador novamente.
O JSON grande do painel é derivado e não precisa ser versionado.

Verificações de código: 32 testes Python e 7 testes Node.js aprovados; rotas
estáticas e API do painel respondendo por HTTP. A inspeção visual no navegador
ficou indisponível: a ferramenta de Computer Use não conseguiu determinar a
URL atual do Chrome com confiança e encerrou a automação.

## Fontes primárias

- [Modelo e suas três classes](https://huggingface.co/pysentimiento/bertweet-pt-sentiment).
- [Pré-processamento dos autores](https://github.com/pysentimiento/pysentimiento/blob/master/pysentimiento/preprocessing.py).
- [Tarefas separadas de sentimento e ironia](https://github.com/pysentimiento/pysentimiento/blob/master/docs/TASKS.md).
- Código executado: `social_preprocessing.py`, `transformer_attribution.py`,
  `band_blocks.py` e `bertweet_validation.py`, em `analise_sentimentos/pipelines/`.
