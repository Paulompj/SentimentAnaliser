import csv
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from analise_sentimentos import cli as project_main
from analise_sentimentos.domain.mention_summary import summarize_mentions
from analise_sentimentos.domain.periods import VIDEO_PUBLISHED_AT_UTC, period_of, window_end
from analise_sentimentos.domain.targets import detect_targets
from analise_sentimentos.pipelines.wordnet import _metrics, evaluate, export_details, import_comments, write_outputs
from analise_sentimentos.pipelines.wordnet_model import Polarity
from analise_sentimentos.sources.collector import CollectionResult, VideoMetadata, YouTubeCollector, parse_utc


START = parse_utc("2022-10-16T23:00:00Z")
END = parse_utc("2022-10-17T04:06:39Z")


class WorkflowTests(unittest.TestCase):
    def test_accuracy_percent_counts_exact_matches(self):
        result = _metrics(
            ["positive", "negative", "neutral", "insufficient_evidence"],
            ["positive", "positive", "neutral", "negative"],
            ("positive", "negative", "neutral", "insufficient_evidence"),
        )
        self.assertEqual(result["n"], 4)
        self.assertEqual(result["correct"], 2)
        self.assertEqual(result["accuracy_percent"], 50.0)

    def test_sentiment_by_mention_keeps_overlap_explicit(self):
        rows = [
            {"sentiment": "positive", "mention_lula": "1", "mention_bolsonaro": "1"},
            {"sentiment": "negative", "mention_lula": "1", "mention_bolsonaro": "0"},
            {"sentiment": "neutral", "mention_lula": "0", "mention_bolsonaro": "0"},
        ]
        groups = {row["grupo"]: row for row in summarize_mentions(rows)}
        self.assertEqual(groups["menciona_lula"]["positive"], 1)
        self.assertEqual(groups["menciona_bolsonaro"]["positive"], 1)
        self.assertEqual(groups["ambos"]["total"], 1)
        self.assertEqual(groups["somente_lula"]["negative"], 1)
        self.assertEqual(sum(groups[name]["total"] for name in
                             ("somente_lula", "somente_bolsonaro", "ambos", "nenhum")), 3)

    def test_main_uses_publication_returned_by_api(self):
        video = VideoMetadata("video", "Título", "2022-10-17T02:00:00Z", None,
                              "2022-10-17T00:52:18Z", 0)
        with patch.object(project_main, "YouTubeCollector") as collector_class, \
             patch.object(project_main, "write_outputs") as write_outputs:
            collector = collector_class.return_value
            collector.video.return_value = video
            collector.collect_window.return_value = CollectionResult([], 1, 0, 0, 0, 0, 0, True)
            write_outputs.return_value = {"collection": {"in_window": 0, "complete": True}}
            with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
                self.assertEqual(project_main.main(["--output", folder]), 0)
            self.assertEqual(collector.collect_window.call_args.args[2],
                             parse_utc("2022-10-17T05:00:00Z"))

    def test_three_hours_after_publication_and_periods(self):
        publication = parse_utc(VIDEO_PUBLISHED_AT_UTC)
        debate_end = parse_utc("2022-10-17T00:52:18Z")
        self.assertEqual(window_end(publication), END)
        self.assertEqual(period_of(debate_end, debate_end, publication), "durante_debate")
        self.assertEqual(period_of(parse_utc("2022-10-17T01:00:00Z"), debate_end, publication),
                         "entre_debate_e_publicacao")
        self.assertEqual(period_of(publication, debate_end, publication), "apos_publicacao")

    def test_target_numbers_do_not_match_years(self):
        self.assertEqual(detect_targets("O debate foi em 2022."), [])
        self.assertEqual(detect_targets("Voto #22, não 13."), ["lula", "bolsonaro"])
        self.assertEqual(detect_targets("Lula e Bolsonaro"), ["lula", "bolsonaro"])
        self.assertEqual(detect_targets("Luiz Inácio e Jair"), ["lula", "bolsonaro"])
        self.assertEqual(detect_targets("bozo criticou Lula"), ["lula", "bolsonaro"])
        self.assertEqual(detect_targets("Flávio Bolsonaro comentou"), [])
        self.assertEqual(detect_targets("Flávio Bolsonaro citou Jair"), ["bolsonaro"])
        self.assertEqual(detect_targets("Flávio Bolsonaro debate Lula", election_year=2026),
                         ["lula", "flavio_bolsonaro"])
        self.assertEqual(detect_targets("Jair Bolsonaro comentou", election_year=2026), [])
        self.assertEqual(detect_targets("Jair Bolsonaro citou Flávio", election_year=2026),
                         ["flavio_bolsonaro"])
        self.assertEqual(detect_targets("Voto 22 e não 13", election_year=2026),
                         ["lula", "flavio_bolsonaro"])

    def test_negation_changes_sentiment(self):
        self.assertEqual(Polarity("Bolsonaro é ótimo")["classificacao"], "positive")
        self.assertEqual(Polarity("Bolsonaro não é ótimo")["classificacao"], "negative")
        self.assertEqual(Polarity("Lula é péssimo")["classificacao"], "negative")
        self.assertEqual(Polarity("Lula não é péssimo")["classificacao"], "positive")
        self.assertEqual(Polarity("...")["classificacao"], "insufficient_evidence")

    def test_window_excludes_late_and_later_edited_comments(self):
        def item(comment_id, published, updated=None):
            return {"snippet": {
                "topLevelComment": {"id": comment_id, "snippet": {
                    "textDisplay": "Comentário", "publishedAt": published,
                    "updatedAt": updated or published, "likeCount": 0,
                }},
                "totalReplyCount": 0,
            }}

        collector = YouTubeCollector(api_key="test-key")
        collector._get = lambda endpoint, **params: {
            "items": [
                item("late", "2026-09-01T00:00:00Z"),
                item("just_after_cutoff", "2022-10-17T04:06:40Z"),
                item("cutoff", "2022-10-17T04:06:39Z"),
                item("after_publication", "2022-10-17T02:00:00Z"),
                item("during", "2022-10-17T00:00:00Z"),
                item("edited", "2022-10-17T00:01:00Z", "2022-10-18T00:00:00Z"),
                item("early", "2022-10-16T22:59:59Z"),
            ],
            "nextPageToken": "unused",
        }
        result = collector.collect_window("video", START, END)
        self.assertTrue(result.complete)
        self.assertEqual([comment.comment_id for comment in result.comments],
                         ["during", "after_publication", "cutoff"])
        self.assertEqual((result.after_window, result.before_window, result.edited_after_window), (2, 1, 1))

    def test_import_and_evaluation_keep_stance_separate(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            directory = Path(folder)
            source = directory / "chat.csv"
            with source.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["comment_id", "text", "published_at"])
                writer.writeheader()
                writer.writerow({"comment_id": "1", "text": "Voto no Lula, Bolsonaro é horrível",
                                 "published_at": "2022-10-17T00:00:00Z"})
                writer.writerow({"comment_id": "2", "text": "Saudades do debate de 2022",
                                 "published_at": "2026-01-01T00:00:00Z"})
            collection = import_comments(source, START, END)
            self.assertEqual(len(collection.comments), 1)
            self.assertEqual(collection.after_window, 1)
            output = directory / "output"
            report = write_outputs(output, None, collection, START, END, "fixture", 10)
            self.assertEqual(report["collection"]["in_window"], 1)
            self.assertEqual(report["period_counts"]["durante_debate"], 1)
            with (output / "avaliacao.json").open(encoding="utf-8") as file:
                self.assertEqual(json.load(file)["status"], "pendente_de_rotulacao_e_nova_avaliacao")
            with (output / "analise.csv").open(encoding="utf-8-sig", newline="") as file:
                row = next(csv.DictReader(file))
            self.assertEqual(row["stance_lula"], "nao_avaliada")
            self.assertEqual(row["stance_bolsonaro"], "nao_avaliada")
            with (output / "analise_detalhada.jsonl").open(encoding="utf-8") as file:
                detail = json.loads(file.readline())
            self.assertEqual(detail["comment_id"], row["comment_id"])
            self.assertEqual(detail["sentiment"], row["sentiment"])
            self.assertEqual(detail["positive_score"], float(row["positive_score"]))
            self.assertTrue(any(token["synsets"] for token in detail["detalhes"]))
            self.assertTrue(all("classe_gramatical" in token for token in detail["detalhes"]))
            with (output / "synsets.csv").open(encoding="utf-8-sig", newline="") as file:
                synset_rows = list(csv.DictReader(file))
            self.assertTrue(any(item["synset"] for item in synset_rows))
            self.assertEqual(export_details(output)["comments"], 1)
            with (output / "rotulacao.csv").open(encoding="utf-8-sig", newline="") as file:
                annotations = list(csv.DictReader(file))
            annotations[0].update(sentimento_geral="negative", posicao_lula="favor",
                                  posicao_bolsonaro="contra", assunto_principal="candidato")
            with (output / "rotulacao.csv").open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(annotations[0]))
                writer.writeheader()
                writer.writerows(annotations)
            with (output / "rotulacao_b.csv").open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(annotations[0]))
                writer.writeheader()
                writer.writerows(annotations)
            result = evaluate(output)
            self.assertEqual(result["human_stance_counts"]["lula"]["favor"], 1)
            self.assertEqual(result["inter_annotator_agreement"]["posicao_lula"]["agreement"], 1.0)
            self.assertIn("indisponível", result["stance_automated_evaluation"])


if __name__ == "__main__":
    unittest.main()
