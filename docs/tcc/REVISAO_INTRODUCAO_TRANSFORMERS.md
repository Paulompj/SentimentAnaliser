# Revisão da introdução

Notas de revisão das duas versões da introdução. Este arquivo não integra o texto do TCC.

## Roteiro e função dos parágrafos

1. **Tarefa e aplicação:** definir a entrada (chat capturado) e a saída (polaridade por mensagem e distribuição por bloco); distinguir chat ao vivo de comentários posteriores.
2. **Trabalho anterior e desafio:** situar a etapa WordNet de 2022 e explicar as dificuldades próprias do novo recorte, sem atribuir uma falha não medida ao método anterior.
3. **Solução aplicada:** identificar o modelo Transformer e justificar sua escolha com o domínio do pré-treinamento.
4. **Fluxo técnico:** expor coleta, divisão por blocos, preparação, classificação, auditoria e inspeção dos resultados; explicar o ganho de rastreabilidade.
5. **Contribuição:** declarar as entregas do estudo e a separação entre polaridade da frase e avaliação de um candidato.
6. **Evidência:** informar cobertura dos cinco arquivos e distribuição prevista nas mensagens comuns dos quatro blocos principais.
7. **Limites:** registrar a lacuna de coleta, a ausência de rótulos humanos e a impossibilidade de inferir apoio político ou opinião do eleitorado.

## Aderência a `references/introduction.md`

O guia oferece versões alternativas para cada parte da introdução e pede a escolha de um molde adequado ao estudo. As duas redações seguem a sequência da seção **Section Skeleton**; não reproduzem literalmente o mapa lógico de artigos que propõem um novo método e o comparam com o estado da arte.

| Item do guia | Tratamento nesta introdução |
| --- | --- |
| Tarefa, aplicação, entrada e saída | Definidas no primeiro parágrafo, no recorte específico do chat ao vivo. |
| Trabalho anterior e desafio técnico | WordNet de 2022 é situado; a linguagem do chat e a ambiguidade do alvo são explicadas. Nenhuma falha comparativa é alegada. |
| Solução e motivo da escolha | Modelo em português identificado; pré-treinamento em textos de redes sociais justifica a aplicação, sem provar acurácia. |
| Vantagem técnica demonstrável | Identificadores, horários, revisão do modelo e auditoria sustentam rastreabilidade e consistência das contagens. |
| Experimento | Cobertura de 24.522 registros, classificação textual e distribuição de previsões por bloco são informadas. |
| Contribuição | Base organizada, fluxo auditável e limite explícito entre polaridade textual e apoio político. |
| Melhoria de métrica e comparação com métodos de ponta | **Não demonstradas.** Faltam rótulos humanos neste chat e um protocolo de comparação na mesma base. O texto não reivindica esses resultados. |

## Mapa de afirmações e evidências

| Afirmação da introdução | Evidência | Estado |
| --- | --- | --- |
| O recorte tem 24.522 registros; 23.594 mensagens comuns e 649 Super Chats com texto foram classificados; 279 registros ficaram sem classificação textual. | `output/2026/bertweet_band/execucao.json`; `docs/RESULTADOS_BERTWEET_BAND.md` | Sustentada |
| Nos quatro blocos principais, 23.477 mensagens comuns receberam 49,76% de previsões neutras, 34,33% negativas e 15,91% positivas. | `docs/RESULTADOS_BERTWEET_BAND.md`; `output/2026/bertweet_band/resumo_blocos.csv` | Sustentada como distribuição de previsões, não como verdade anotada |
| O modelo usado produz as classes positiva, neutra e negativa e se baseia no BERTabaporu. | Ficha de `pysentimiento/bertweet-pt-sentiment`; Costa et al. (2023) | Sustentada |
| A auditoria reconcilia as entradas e saídas e reproduz uma amostra das inferências. | `docs/VALIDACAO_BERTWEET.md`; `output/2026/bertweet_validacao/auditoria.json` | Sustentada como consistência técnica |
| Houve uma lacuna de cerca de 9 min 38 s que atravessou o fim do segundo bloco. | `output/2026/lacunas_coleta.json`; `output/2026/blocos.json` | Sustentada |
| Não há estimativa de acurácia do classificador nesse chat. | `docs/VALIDACAO_BERTWEET.md`; 500 linhas da amostra sem rótulo humano | Sustentada; avaliação humana pendente |
| As contagens não estimam apoio político ou opinião do eleitorado. | O modelo classifica o texto inteiro; a amostra é restrita a mensagens capturadas e não constitui amostra probabilística do eleitorado. | Limite de inferência explicitado |

## Autoavaliação da seção

| Dimensão | Pergunta e resposta |
| --- | --- |
| Contribuição | O texto identifica a contribuição? Sim: aplicação auditável do classificador a um chat organizado por blocos. Não reivindica um novo modelo. |
| Clareza | É possível entender entrada, saída e sequência do fluxo? Sim; os detalhes operacionais pertencem à metodologia. |
| Força experimental | Há evidência de desempenho superior ao WordNet? Não. O texto não afirma melhoria nem faz comparação direta entre bases diferentes. |
| Avaliação | Há acurácia medida contra referência humana? Não. As 500 mensagens ainda precisam ser anotadas e avaliadas. |
| Desenho do método | A polaridade textual é separada de apoio a candidato? Sim. A lacuna de coleta e a ausência de representatividade também estão registradas. |

## Checagem final

- Clareza e fluxo: cada parágrafo abre com sua mensagem central; a ordem segue tarefa, trabalho anterior e desafio, solução, fluxo, contribuição, evidência e limites.
- Terminologia: “polaridade”, “previsão” e “mensagem capturada” são usados de modo consistente.
- Afirmações sem prova: nenhuma melhoria de acurácia, apoio eleitoral ou generalização populacional é reivindicada.
- Evidência ainda necessária: rotulação humana das 500 mensagens para medir desempenho semântico no corpus de 2026.
