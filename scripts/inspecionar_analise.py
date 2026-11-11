"""Mostra texto, escores e synsets de um comentário da análise detalhada."""

import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path(__file__).resolve().parents[1] / "output" / "analise_detalhada.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--numero", type=int, default=1, help="Posição no arquivo, a partir de 1")
    choice.add_argument("--id", dest="comment_id", help="ID da coluna comment_id em analise.csv")
    args = parser.parse_args()
    if args.numero is not None and args.numero < 1:
        parser.error("--numero deve ser >= 1")

    try:
        with args.input.open(encoding="utf-8") as file:
            record = None
            for index, line in enumerate(file, 1):
                if not args.comment_id and index != args.numero:
                    continue
                candidate = json.loads(line)
                if args.comment_id and candidate["comment_id"] != args.comment_id:
                    continue
                record = candidate
                break
    except OSError as exc:
        parser.error(str(exc))
    if record is None:
        parser.error("comentário não encontrado na análise detalhada")

    print(f"ID: {record['comment_id']}")
    print(f"Data: {record['published_at']} | Período: {record['periodo']}")
    print(f"Texto: {record['text']}")
    print(f"Sentimento: {record['sentiment']}")
    print(f"Score positivo total: {record['positive_score']:.6f}")
    print(f"Score negativo total: {record['negative_score']:.6f}")
    print("\nTermos considerados:")
    for token in record["detalhes"]:
        print(f"- [{token['indice_token']}] {token['palavra']} | lema={token['lema']} "
              f"| POS={token['classe_gramatical']} | negado={token['negado']} "
              f"| contribuição=+{token['pos_score']:.6f}/-{token['neg_score']:.6f}")
        if not token["synsets"]:
            print("    sem synset com escore lexical")
        for synset in token["synsets"]:
            print(f"    {synset['synset']}: pos={synset['pos']:.6f}, "
                  f"neg={synset['neg']:.6f}, obj={synset['obj']:.6f}")
    if not record["detalhes"]:
        print("  nenhum termo com classe gramatical elegível")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
