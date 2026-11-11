"""Gera pizzas do sentimento geral para comentários que mencionam candidatos."""

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output" / "sentimento_por_mencao.csv"
OUTPUT = ROOT / "output" / "grafico_pizza_sentimento_por_mencao"
CLASSES = (
    ("positive", "Positivo", "#087F5B"),
    ("negative", "Negativo", "#C4474D"),
    ("neutral", "Neutro", "#A47B13"),
    ("insufficient_evidence", "Sem evidência", "#AEB8C2"),
)


def inteiro(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def percentual(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def ler_dados() -> dict[str, dict[str, int]]:
    with SOURCE.open(encoding="utf-8-sig", newline="") as arquivo:
        dados = {
            linha["grupo"]: {chave: int(valor) for chave, valor in linha.items() if chave != "grupo"}
            for linha in csv.DictReader(arquivo)
        }
    for grupo in ("menciona_lula", "menciona_bolsonaro", "ambos"):
        if grupo not in dados:
            raise ValueError(f"Grupo ausente no CSV: {grupo}")
        total = sum(dados[grupo][chave] for chave, _, _ in CLASSES)
        if total != dados[grupo]["total"]:
            raise ValueError(f"Total inconsistente no grupo {grupo}: {total} != {dados[grupo]['total']}")
    return dados


def main() -> None:
    dados = ler_dados()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11})
    figura, eixos = plt.subplots(1, 2, figsize=(12.6, 7.5), facecolor="white")
    figura.subplots_adjust(left=0.04, right=0.96, top=0.77, bottom=0.26, wspace=0.14)

    figura.suptitle(
        "Sentimento geral dos comentários com menção a cada candidato",
        x=0.5, y=0.95, fontsize=17, fontweight="bold", color="#202B33"
    )
    figura.text(
        0.5, 0.89,
        "Publicados de 16/10/2022, 20h, a 17/10/2022, 01h06 (horário de Brasília)",
        ha="center", fontsize=10.5, color="#52616B"
    )

    for eixo, (grupo, titulo) in zip(
        eixos, (("menciona_lula", "Menciona Lula"), ("menciona_bolsonaro", "Menciona Bolsonaro"))
    ):
        linha = dados[grupo]
        valores = [linha[chave] for chave, _, _ in CLASSES]
        fatias, _, porcentagens = eixo.pie(
            valores,
            colors=[cor for _, _, cor in CLASSES],
            startangle=90,
            counterclock=False,
            autopct=lambda valor: f"{percentual(valor)}%",
            pctdistance=0.79,
            wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2},
        )
        for indice, rotulo in enumerate(porcentagens):
            rotulo.set_color("#22303A" if indice == 3 else "white")
            rotulo.set_fontsize(10.5)
            rotulo.set_fontweight("bold")

        eixo.text(0, 0.07, inteiro(linha["total"]), ha="center", va="center",
                  fontsize=21, fontweight="bold", color="#202B33")
        eixo.text(0, -0.15, "comentários", ha="center", va="center",
                  fontsize=10, color="#52616B")
        eixo.set_title(titulo, pad=20, fontsize=14, fontweight="bold", color="#202B33")
        eixo.legend(
            fatias,
            [f"{nome}: {inteiro(linha[chave])}" for chave, nome, _ in CLASSES],
            loc="upper center", bbox_to_anchor=(0.5, -0.05),
            ncol=2, frameon=False, fontsize=10, columnspacing=1.8,
            handlelength=1.1, handletextpad=0.5, labelspacing=0.8,
        )

    figura.text(
        0.5, 0.105,
        f"{inteiro(dados['ambos']['total'])} comentários citam ambos e aparecem nas duas pizzas; percentuais usam o total de cada pizza.",
        ha="center", fontsize=10, color="#374650"
    )
    figura.text(
        0.5, 0.072,
        "Sentimento do comentário inteiro; menção não mede apoio ao candidato. Método lexical ainda sem validação humana.",
        ha="center", fontsize=9.7, color="#52616B"
    )
    figura.text(
        0.5, 0.039, "Fonte: output/sentimento_por_mencao.csv", ha="center",
        fontsize=9, color="#65737C"
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(OUTPUT.with_suffix(".png"), dpi=220, facecolor="white")
    figura.savefig(OUTPUT.with_suffix(".pdf"), facecolor="white")
    plt.close(figura)
    print(f"Gráficos salvos em {OUTPUT.with_suffix('.png')} e {OUTPUT.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
