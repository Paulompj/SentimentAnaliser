# Análise dos comentários do debate e da repercussão inicial

- Fonte: YouTube Data API v3 / commentThreads.list (comentários principais)
- Janela: 16/10/2022 20:00:00 UTC-03 a 17/10/2022 01:06:39 UTC-03
- Comentários examinados: 33153
- Comentários elegíveis: 15088
- Durante o debate: 0
- Entre o fim do debate e a publicação do vídeo: 2341
- Desde a publicação do vídeo: 12747
- Comentários posteriores ao período: 18005
- Coleta completa até o início da janela: sim
- Excluídos por edição posterior: 60

- Publicação do vídeo na API: 16/10/2022 22:06:39 UTC-03
- Encerramento da transmissão na API: 16/10/2022 21:52:18 UTC-03

## Sentimento geral (linha de base automática)

- positive: 5944
- negative: 3148
- neutral: 1494
- insufficient_evidence: 4502

## Menções explícitas detectadas

- Lula: 4983
- Bolsonaro: 6735
- Ambos: 1581

## Limitações

- O início às 20h é o horário anunciado pela Band; o minuto exato da primeira fala não foi verificado.
- Comentários após o fim da transmissão representam repercussão posterior, não reações publicadas durante o debate.
- O publishedAt do vídeo é o marco da janela; ele não prova quando a página da transmissão começou a aceitar comentários.
- A polaridade é do comentário inteiro; não representa apoio ou oposição a candidato.
- Posição por candidato permanece 'nao_avaliada' até haver rótulos humanos e validação.
- A linha de base SentiWordNet não resolve ironia, gírias nem todos os sentidos no contexto.
- A identificação por nomes e apelidos explícitos perde referências indiretas.
- A API commentThreads retorna comentários principais; chat ao vivo e respostas são fontes distintas.
- Comentários removidos, privados ou indisponíveis na data da coleta não podem ser recuperados.
- A amostra de rotulagem é balanceada por menção e não serve para estimar proporções populacionais.
