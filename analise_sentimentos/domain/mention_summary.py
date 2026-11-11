"""Cruza sentimento geral com menções explícitas, sem inferir apoio político."""

import csv
from collections import Counter
from pathlib import Path


LABELS = ("positive", "negative", "neutral", "insufficient_evidence")
GROUPS = ("menciona_lula", "menciona_bolsonaro", "somente_lula",
          "somente_bolsonaro", "ambos", "nenhum")


def summarize_mentions(rows: list[dict]) -> list[dict]:
    counts = {group: Counter() for group in GROUPS}
    for row in rows:
        sentiment = row["sentiment"]
        if sentiment not in LABELS:
            raise ValueError(f"Rótulo de sentimento inválido: {sentiment}")
        lula = row["mention_lula"] == "1"
        bolsonaro = row["mention_bolsonaro"] == "1"
        exclusive = "ambos" if lula and bolsonaro else "somente_lula" if lula else \
                    "somente_bolsonaro" if bolsonaro else "nenhum"
        counts[exclusive][sentiment] += 1
        if lula:
            counts["menciona_lula"][sentiment] += 1
        if bolsonaro:
            counts["menciona_bolsonaro"][sentiment] += 1
    return [{"grupo": group, "total": sum(counts[group].values()),
             **{label: counts[group][label] for label in LABELS}} for group in GROUPS]


def write_mention_summary(output: Path, rows: list[dict] | None = None) -> list[dict]:
    """Gera tabela e explicação a partir da análise existente, sem usar a API."""
    if rows is None:
        with (output / "analise.csv").open(encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    summary = summarize_mentions(rows)
    fields = ["grupo", "total", *LABELS]
    with (output / "sentimento_por_mencao.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary)
    lines = [
        "# Sentimento geral por grupo de menção",
        "",
        "| Grupo | Total | Positivo | Negativo | Neutro | Sem evidência lexical |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary:
        lines.append(f"| {row['grupo']} | {row['total']} | {row['positive']} | "
                     f"{row['negative']} | {row['neutral']} | {row['insufficient_evidence']} |")
    lines += [
        "",
        "As linhas `menciona_lula` e `menciona_bolsonaro` se sobrepõem quando um comentário cita os dois.",
        "As quatro linhas `somente_lula`, `somente_bolsonaro`, `ambos` e `nenhum` são exclusivas e somam o total analisado.",
        "O sentimento se refere ao comentário inteiro. Positivo não significa favorável ao candidato mencionado; negativo não significa contrário a ele.",
        "A posição sobre cada candidato continua `nao_avaliada` até haver rotulagem humana e um método validado.",
    ]
    (output / "relatorio_por_mencao.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
