"""Pipeline WordNet: análise léxica, exportação, amostragem e avaliação."""

from __future__ import annotations

import csv
import json
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from analise_sentimentos.domain.mention_summary import write_mention_summary
from analise_sentimentos.domain.periods import DEBATE_END_UTC, PERIODS, VIDEO_PUBLISHED_AT_UTC, period_of
from analise_sentimentos.domain.targets import detect_targets
from analise_sentimentos.pipelines.wordnet_model import Polarity
from analise_sentimentos.sources.collector import CollectionResult, Comment, VideoMetadata, parse_utc


BRT = timezone(timedelta(hours=-3))
SENTIMENT_LABELS = ("positive", "negative", "neutral", "insufficient_evidence")
STANCE_LABELS = ("favor", "contra", "sem_posicao", "incerto", "nao_citado")
TOPIC_LABELS = ("candidato", "debate", "band", "outro", "incerto")


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _str_brt(value: datetime) -> str:
    return value.astimezone(BRT).strftime("%d/%m/%Y %H:%M:%S UTC-03")


def import_comments(path: Path, start: datetime, end: datetime) -> CollectionResult:
    """Importa arquivo externo de chat/comentários sem presumir cobertura completa."""
    required = {"comment_id", "text", "published_at"}
    comments = []
    seen = set()
    inspected = after = before = edited_after = duplicates = 0
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"CSV precisa das colunas: {', '.join(sorted(required))}")
        for row in reader:
            comment_id = row["comment_id"]
            if comment_id in seen:
                duplicates += 1
                continue
            seen.add(comment_id)
            inspected += 1
            published = parse_utc(row["published_at"])
            if published > end:
                after += 1
                continue
            if published < start:
                before += 1
                continue
            updated_text = row.get("updated_at") or row["published_at"]
            if parse_utc(updated_text) > end:
                edited_after += 1
                continue
            comments.append(Comment(
                comment_id=comment_id,
                text=row["text"],
                published_at=row["published_at"],
                updated_at=updated_text,
                like_count=int(row.get("like_count") or 0),
                reply_count=int(row.get("reply_count") or 0),
            ))
    comments.sort(key=lambda item: (item.published_at, item.comment_id))
    return CollectionResult(comments, 0, inspected, after, before, edited_after, duplicates, False)


def _sample_rows(rows: list[dict], size: int) -> list[dict]:
    """Amostra de validação balanceada por tipo de menção, com semente fixa."""
    randomizer = random.Random(20221016)
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        lula = row["mention_lula"] == "1"
        bolsonaro = row["mention_bolsonaro"] == "1"
        group = "ambos" if lula and bolsonaro else "lula" if lula else "bolsonaro" if bolsonaro else "nenhum"
        groups[group].append(row)
    for group in groups.values():
        randomizer.shuffle(group)
    selected = []
    order = ("ambos", "lula", "bolsonaro", "nenhum")
    while len(selected) < min(size, len(rows)):
        took_one = False
        for name in order:
            if groups[name] and len(selected) < size:
                selected.append(groups[name].pop())
                took_one = True
        if not took_one:
            break
    selected.sort(key=lambda row: (row["published_at"], row["comment_id"]))
    return selected


SYNSET_FIELDS = ["comment_id", "indice_token", "palavra", "lema", "classe_gramatical",
                 "negado", "pos_score_token", "neg_score_token", "synset",
                 "pos_score_synset", "neg_score_synset", "obj_score_synset"]


def _write_explanations(
    output: Path, records: Iterable[tuple[dict, dict]], total: int,
) -> dict[str, int]:
    """Grava detalhes por comentário e por synset sem manter tudo na memória."""
    detail_tmp = output / "analise_detalhada.jsonl.tmp"
    synset_tmp = output / "synsets.csv.tmp"
    processed = terms = synset_count = 0
    print(f"Analisando sentimento de {total} comentários...", flush=True)
    with detail_tmp.open("w", encoding="utf-8", newline="") as detail_file, \
         synset_tmp.open("w", encoding="utf-8-sig", newline="") as synset_file:
        writer = csv.DictWriter(synset_file, fieldnames=SYNSET_FIELDS)
        writer.writeheader()
        for row, sentiment in records:
            detail_file.write(json.dumps({
                "comment_id": row["comment_id"],
                "published_at": row["published_at"],
                "periodo": row.get("periodo", ""),
                "text": row["text"],
                "sentiment": row["sentiment"],
                "positive_score": float(row["positive_score"]),
                "negative_score": float(row["negative_score"]),
                "detalhes": sentiment["detalhes"],
            }, ensure_ascii=False) + "\n")
            for token in sentiment["detalhes"]:
                terms += 1
                synsets = token["synsets"]
                synset_count += len(synsets)
                for synset in synsets or [None]:
                    writer.writerow({
                        "comment_id": row["comment_id"],
                        "indice_token": token["indice_token"],
                        "palavra": token["palavra"],
                        "lema": token["lema"],
                        "classe_gramatical": token["classe_gramatical"],
                        "negado": int(token["negado"]),
                        "pos_score_token": token["pos_score"],
                        "neg_score_token": token["neg_score"],
                        "synset": synset["synset"] if synset else "",
                        "pos_score_synset": synset["pos"] if synset else "",
                        "neg_score_synset": synset["neg"] if synset else "",
                        "obj_score_synset": synset["obj"] if synset else "",
                    })
            processed += 1
            if processed % 500 == 0 or processed == total:
                print(f"Sentimento: {processed}/{total} comentários analisados", flush=True)
    if processed != total:
        raise ValueError(f"Esperados {total} comentários; processados {processed}")
    detail_tmp.replace(output / "analise_detalhada.jsonl")
    synset_tmp.replace(output / "synsets.csv")
    return {"comments": processed, "terms": terms, "synsets": synset_count}


def export_details(output: Path) -> dict[str, int]:
    """Recria explicações da análise existente sem consultar a API novamente."""
    with (output / "analise.csv").open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"comment_id", "published_at", "text", "sentiment",
                    "positive_score", "negative_score"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("analise.csv não contém as colunas necessárias")
        rows = list(reader)

    def recompute() -> Iterable[tuple[dict, dict]]:
        for row in rows:
            sentiment = Polarity(row["text"])
            if (sentiment["classificacao"] != row["sentiment"] or
                round(sentiment["pos_total"], 6) != float(row["positive_score"]) or
                round(sentiment["neg_total"], 6) != float(row["negative_score"])):
                raise ValueError(f"Scores divergentes para {row['comment_id']}; execute main.py novamente")
            yield row, sentiment

    return _write_explanations(output, recompute(), len(rows))


def write_outputs(
    output: Path,
    video: VideoMetadata | None,
    collection: CollectionResult,
    start: datetime,
    end: datetime,
    source: str,
    sample_size: int,
) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    debate_end = parse_utc(video.live_end_at) if video and video.live_end_at else parse_utc(DEBATE_END_UTC)
    publication = parse_utc(video.published_at) if video else parse_utc(VIDEO_PUBLISHED_AT_UTC)

    def period(item: Comment) -> str:
        return period_of(parse_utc(item.published_at), debate_end, publication)

    raw_rows = [
        {
            "comment_id": item.comment_id,
            "text": item.text,
            "published_at": item.published_at,
            "updated_at": item.updated_at,
            "like_count": item.like_count,
            "reply_count": item.reply_count,
            "periodo": period(item),
        }
        for item in collection.comments
    ]
    _write_csv(output / "coleta.csv", list(raw_rows[0]) if raw_rows else
               ["comment_id", "text", "published_at", "updated_at", "like_count", "reply_count", "periodo"], raw_rows)

    results = []

    def analyze() -> Iterable[tuple[dict, dict]]:
        for item in collection.comments:
            sentiment = Polarity(item.text)
            targets = detect_targets(item.text)
            row = {
                "comment_id": item.comment_id,
                "published_at": item.published_at,
                "text": item.text,
                "periodo": period(item),
                "sentiment": sentiment["classificacao"],
                "positive_score": round(sentiment["pos_total"], 6),
                "negative_score": round(sentiment["neg_total"], 6),
                "mention_lula": "1" if "lula" in targets else "0",
                "mention_bolsonaro": "1" if "bolsonaro" in targets else "0",
                "stance_lula": "nao_avaliada",
                "stance_bolsonaro": "nao_avaliada",
            }
            results.append(row)
            yield row, sentiment

    _write_explanations(output, analyze(), len(collection.comments))
    result_fields = ["comment_id", "published_at", "text", "periodo", "sentiment", "positive_score",
                     "negative_score", "mention_lula", "mention_bolsonaro",
                     "stance_lula", "stance_bolsonaro"]
    _write_csv(output / "analise.csv", result_fields, results)
    write_mention_summary(output, results)

    selected = _sample_rows(results, sample_size)
    label_fields = ["comment_id", "published_at", "text", "periodo", "sentimento_geral",
                    "posicao_lula", "posicao_bolsonaro", "assunto_principal"]
    second_rater = random.Random(160).sample(selected, min(len(selected), max(1, round(len(selected) * 0.25)))) if selected else []
    for filename, sample in (("rotulacao.csv", selected), ("rotulacao_b.csv", second_rater)):
        labels_path = output / filename
        has_annotation_rows = False
        if labels_path.exists():
            with labels_path.open(encoding="utf-8-sig", newline="") as file:
                has_annotation_rows = any(csv.DictReader(file))
        if not has_annotation_rows:
            annotation_rows = [
                {
                    "comment_id": row["comment_id"],
                    "published_at": row["published_at"],
                    "text": row["text"],
                    "periodo": row["periodo"],
                    "sentimento_geral": "",
                    "posicao_lula": "",
                    "posicao_bolsonaro": "",
                    "assunto_principal": "",
                }
                for row in sample
            ]
            _write_csv(labels_path, label_fields, annotation_rows)

    counts = Counter(row["sentiment"] for row in results)
    period_counts = Counter(row["periodo"] for row in results)
    report = {
        "source": source,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "window_start_utc": start.astimezone(timezone.utc).isoformat(),
        "window_end_utc": end.astimezone(timezone.utc).isoformat(),
        "debate_end_utc": debate_end.isoformat(),
        "video_published_at_utc": publication.isoformat(),
        "video": vars(video) if video else None,
        "collection": {
            "pages": collection.pages,
            "inspected": collection.inspected,
            "in_window": len(collection.comments),
            "after_window": collection.after_window,
            "before_window": collection.before_window,
            "edited_after_window": collection.edited_after_window,
            "duplicates": collection.duplicates,
            "complete": collection.complete,
        },
        "sentiment_counts": {label: counts[label] for label in SENTIMENT_LABELS},
        "period_counts": {label: period_counts[label] for label in PERIODS},
        "explicit_mentions": {
            "lula": sum(row["mention_lula"] == "1" for row in results),
            "bolsonaro": sum(row["mention_bolsonaro"] == "1" for row in results),
            "both": sum(row["mention_lula"] == "1" and row["mention_bolsonaro"] == "1" for row in results),
        },
        "annotation_sample_size": len(selected),
        "second_rater_sample_size": len(second_rater),
    }
    (output / "resumo.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Análise dos comentários do debate e da repercussão inicial",
        "",
        f"- Fonte: {source}",
        f"- Janela: {_str_brt(start)} a {_str_brt(end)}",
        f"- Comentários examinados: {collection.inspected}",
        f"- Comentários elegíveis: {len(collection.comments)}",
        f"- Durante o debate: {period_counts['durante_debate']}",
        f"- Entre o fim do debate e a publicação do vídeo: {period_counts['entre_debate_e_publicacao']}",
        f"- Desde a publicação do vídeo: {period_counts['apos_publicacao']}",
        f"- Comentários posteriores ao período: {collection.after_window}",
        f"- Coleta completa até o início da janela: {'sim' if collection.complete else 'não'}",
        f"- Excluídos por edição posterior: {collection.edited_after_window}",
        "",
    ]
    if video:
        lines += [
            f"- Publicação do vídeo na API: {_str_brt(parse_utc(video.published_at))}",
            f"- Encerramento da transmissão na API: {_str_brt(parse_utc(video.live_end_at)) if video.live_end_at else 'não informado'}",
            "",
        ]
    if collection.comments:
        lines += ["## Sentimento geral (linha de base automática)", ""]
        lines += [f"- {label}: {counts[label]}" for label in SENTIMENT_LABELS]
        lines += [
            "", "## Menções explícitas detectadas", "",
            f"- Lula: {report['explicit_mentions']['lula']}",
            f"- Bolsonaro: {report['explicit_mentions']['bolsonaro']}",
            f"- Ambos: {report['explicit_mentions']['both']}", "",
        ]
    else:
        lines += [
            "## Resultado do recorte", "",
            "**Nenhum comentário elegível foi encontrado para este recorte nesta fonte.**",
            "",
        ]
    lines += [
        "## Limitações", "",
        "- O início às 20h é o horário anunciado pela Band; o minuto exato da primeira fala não foi verificado.",
        "- Comentários após o fim da transmissão representam repercussão posterior, não reações publicadas durante o debate.",
        "- O publishedAt do vídeo é o marco da janela; ele não prova quando a página da transmissão começou a aceitar comentários.",
        "- A polaridade é do comentário inteiro; não representa apoio ou oposição a candidato.",
        "- Posição por candidato permanece 'nao_avaliada' até haver rótulos humanos e validação.",
        "- A linha de base SentiWordNet não resolve ironia, gírias nem todos os sentidos no contexto.",
        "- A identificação por nomes e apelidos explícitos perde referências indiretas.",
        "- A API commentThreads retorna comentários principais; chat ao vivo e respostas são fontes distintas.",
        "- Comentários removidos, privados ou indisponíveis na data da coleta não podem ser recuperados.",
        "- A amostra de rotulagem é balanceada por menção e não serve para estimar proporções populacionais.",
    ]
    if not collection.complete:
        lines.append("- A coleta não confirmou cobertura completa do intervalo.")
    (output / "relatorio.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "avaliacao.json").write_text(json.dumps({
        "status": "pendente_de_rotulacao_e_nova_avaliacao",
        "window_end_utc": report["window_end_utc"],
        "message": "Preencha os rótulos humanos e execute main.py evaluate para calcular métricas deste recorte.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _metrics(gold: list[str], predicted: list[str], labels: tuple[str, ...]) -> dict:
    matrix = {actual: {pred: 0 for pred in labels} for actual in labels}
    for actual, pred in zip(gold, predicted):
        matrix[actual][pred] += 1
    by_class = {}
    for label in labels:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted_count = sum(matrix[actual][label] for actual in labels)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        by_class[label] = {"precision": round(precision, 4), "recall": round(recall, 4),
                           "f1": round(f1, 4), "support": support}
    present = [item["f1"] for item in by_class.values() if item["support"]]
    correct = sum(matrix[label][label] for label in labels)
    return {"n": len(gold), "correct": correct,
            "accuracy_percent": round(100 * correct / len(gold), 2) if gold else None,
            "by_class": by_class, "confusion_matrix": matrix,
            "macro_f1": round(sum(present) / len(present), 4) if present else None}


def _agreement(first: list[str], second: list[str], labels: tuple[str, ...]) -> dict | None:
    if not first:
        return None
    n = len(first)
    observed = sum(a == b for a, b in zip(first, second)) / n
    first_counts, second_counts = Counter(first), Counter(second)
    chance = sum(first_counts[label] * second_counts[label] for label in labels) / (n * n)
    kappa = (observed - chance) / (1 - chance) if chance < 1 else None
    return {"n": n, "agreement": round(observed, 4),
            "cohen_kappa": round(kappa, 4) if kappa is not None else None}


def evaluate(output: Path) -> dict:
    """Avalia apenas tarefas para as quais existem rótulos e previsões."""
    with (output / "analise.csv").open(encoding="utf-8-sig", newline="") as file:
        predictions = {row["comment_id"]: row for row in csv.DictReader(file)}
    with (output / "rotulacao.csv").open(encoding="utf-8-sig", newline="") as file:
        annotated = list(csv.DictReader(file))
    second_path = output / "rotulacao_b.csv"
    if second_path.exists():
        with second_path.open(encoding="utf-8-sig", newline="") as file:
            second_labels = {row["comment_id"]: row for row in csv.DictReader(file)}
    else:
        second_labels = {}
    sentiment_gold = []
    sentiment_pred = []
    mention_gold = {name: [] for name in ("lula", "bolsonaro")}
    mention_pred = {name: [] for name in ("lula", "bolsonaro")}
    stance_counts = {name: Counter() for name in ("lula", "bolsonaro")}
    paired = {field: ([], []) for field in ("sentimento_geral", "posicao_lula", "posicao_bolsonaro", "assunto_principal")}
    for row in annotated:
        prediction = predictions.get(row["comment_id"])
        if prediction is None:
            continue
        second = second_labels.get(row["comment_id"], {})
        for field, allowed in (("sentimento_geral", SENTIMENT_LABELS),
                               ("posicao_lula", STANCE_LABELS),
                               ("posicao_bolsonaro", STANCE_LABELS),
                               ("assunto_principal", TOPIC_LABELS)):
            first_label = row[field].strip()
            second_label = second.get(field, "").strip()
            if first_label in allowed and second_label in allowed:
                paired[field][0].append(first_label)
                paired[field][1].append(second_label)
        label = row["sentimento_geral"].strip()
        if label in SENTIMENT_LABELS:
            sentiment_gold.append(label)
            sentiment_pred.append(prediction["sentiment"])
        for name in ("lula", "bolsonaro"):
            stance = row[f"posicao_{name}"].strip()
            if stance in STANCE_LABELS:
                stance_counts[name][stance] += 1
                mention_gold[name].append("0" if stance == "nao_citado" else "1")
                mention_pred[name].append(prediction[f"mention_{name}"])
    results = {
        "sentiment": _metrics(sentiment_gold, sentiment_pred, SENTIMENT_LABELS) if sentiment_gold else None,
        "target_detection": {
            name: _metrics(mention_gold[name], mention_pred[name], ("0", "1")) if mention_gold[name] else None
            for name in ("lula", "bolsonaro")
        },
        "human_stance_counts": {name: dict(counts) for name, counts in stance_counts.items()},
        "inter_annotator_agreement": {
            field: _agreement(first, second, allowed)
            for field, (first, second), allowed in (
                ("sentimento_geral", paired["sentimento_geral"], SENTIMENT_LABELS),
                ("posicao_lula", paired["posicao_lula"], STANCE_LABELS),
                ("posicao_bolsonaro", paired["posicao_bolsonaro"], STANCE_LABELS),
                ("assunto_principal", paired["assunto_principal"], TOPIC_LABELS),
            )
        },
        "stance_automated_evaluation": "indisponível: não existe classificador de posição treinado e validado",
    }
    (output / "avaliacao.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results
