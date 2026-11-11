import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.coletar_comentarios_2026 import collect_published_comments
from scripts.exportar_blocos_chat import export_blocks
from analise_sentimentos.sources.collector import CollectionResult, Comment, VideoMetadata
from analise_sentimentos.sources.live_chat import CSV_FIELDS, _save_state, collect_live_chat, video_id_from_url


VIDEO_ID = "abcdefghijk"


class FakeResponse:
    ok = True
    status_code = 200

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


def message(message_id, text):
    return {
        "id": message_id,
        "snippet": {
            "type": "textMessageEvent",
            "publishedAt": "2026-10-18T23:05:00Z",
            "textMessageDetails": {"messageText": text},
        },
        "authorDetails": {"channelId": "canal", "displayName": "Pessoa"},
    }


class LiveChatTests(unittest.TestCase):
    def test_state_save_retries_transient_windows_file_lock(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            target = Path(folder) / "chat_estado.json"
            target.write_text('{"old": true}', encoding="utf-8")
            original_replace = Path.replace
            attempts = 0

            def replace_after_lock(source, destination):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError("arquivo temporariamente em uso")
                return original_replace(source, destination)

            with patch.object(Path, "replace", replace_after_lock), patch("analise_sentimentos.sources.live_chat.time.sleep"):
                _save_state(target, {"phase": "collecting"})
            self.assertEqual(attempts, 2)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")),
                             {"phase": "collecting"})

    def test_export_blocks_uses_published_time_and_preserves_raw_csv(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            output = Path(folder)
            blocks = [
                {"id": "aaaaaaaa-1111", "name": "Bloco 1: perguntas", "video_id": VIDEO_ID,
                 "started_at_utc": "2026-10-18T23:00:00Z", "ended_at_utc": "2026-10-18T23:10:00Z"},
                {"id": "bbbbbbbb-2222", "name": "Bloco 2", "video_id": VIDEO_ID,
                 "started_at_utc": "2026-10-18T23:10:00Z", "ended_at_utc": "2026-10-18T23:20:00Z"},
            ]
            (output / "blocos.json").write_text(json.dumps(blocks), encoding="utf-8")
            with (output / "chat_ao_vivo.csv").open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
                writer.writeheader()
                for number, published in enumerate(("2026-10-18T23:05:00Z",
                                                    "2026-10-18T23:10:00Z",
                                                    "2026-10-18T23:25:00Z"), 1):
                    writer.writerow({"message_id": f"m{number}", "video_id": VIDEO_ID,
                                     "published_at": published, "text": f"Mensagem {number}"})
            report = export_blocks(output)
            self.assertEqual([item["messages"] for item in report], [1, 1])
            with (output / "blocos" / report[1]["file"]).open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual([row["message_id"] for row in csv.DictReader(file)], ["m2"])
            with (output / "chat_ao_vivo.csv").open(encoding="utf-8-sig", newline="") as file:
                self.assertEqual(len(list(csv.DictReader(file))), 3)

    def test_video_links(self):
        for value in (VIDEO_ID, f"https://youtu.be/{VIDEO_ID}",
                      f"https://www.youtube.com/watch?v={VIDEO_ID}&t=1",
                      f"https://youtube.com/live/{VIDEO_ID}"):
            self.assertEqual(video_id_from_url(value), VIDEO_ID)
        with self.assertRaises(ValueError):
            video_id_from_url("https://example.com/watch?v=abcdefghijk")

    def test_saves_each_page_deduplicates_and_marks_end(self):
        client = Mock(api_key="test-key")
        client._get.return_value = {
            "items": [{"snippet": {"title": "Debate 2026"},
                       "liveStreamingDetails": {"activeLiveChatId": "chat-1"}}],
        }
        client.session.get.side_effect = [
            FakeResponse({"items": [message("m1", "Lula"), message("m2", "Flávio")],
                          "nextPageToken": "page-2", "pollingIntervalMillis": 1000}),
            FakeResponse({"items": [message("m2", "Flávio"), message("m3", "Debate")],
                          "nextPageToken": "page-3", "offlineAt": "2026-10-19T00:00:00Z"}),
        ]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            output = Path(folder)
            state = collect_live_chat(VIDEO_ID, output, client=client, sleep=lambda _: None)
            self.assertTrue(state["complete"])
            self.assertEqual(state["phase"], "finished")
            self.assertEqual(state["total_messages"], 3)
            self.assertEqual([batch["messages"] for batch in state["recent_batches"]], [2, 1])
            self.assertEqual(state["next_page_token"], "page-3")
            with (output / "chat_ao_vivo.csv").open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual([row["message_id"] for row in rows], ["m1", "m2", "m3"])
            self.assertEqual(rows[0]["text"], "Lula")
            self.assertEqual(rows[0]["message_type"], "textMessageEvent")
            stored = json.loads((output / "chat_estado.json").read_text(encoding="utf-8"))
            self.assertTrue(stored["complete"])
            self.assertEqual(collect_live_chat(VIDEO_ID, output, client=client)["total_messages"], 3)
            self.assertEqual(client.session.get.call_count, 2)

    def test_posted_comments_are_separate_and_need_a_real_publication_time(self):
        client = Mock()
        client.video.return_value = VideoMetadata(VIDEO_ID, "Arquivo do debate",
                                                   "2022-10-16T20:00:00Z", None,
                                                   "2022-10-17T00:00:00Z", 1)
        client.collect_window.return_value = CollectionResult(
            [Comment("c1", "Comentário após postagem", "2022-10-17T02:00:00Z",
                     "2022-10-17T02:00:00Z", 0, 0)],
            1, 1, 0, 0, 0, 0, True)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            output = Path(folder)
            with self.assertRaises(ValueError):
                collect_published_comments(VIDEO_ID, output, client=client)
            report = collect_published_comments(
                VIDEO_ID, output, published_at="2022-10-17T01:00:00Z", client=client)
            self.assertEqual(report["eligible"], 1)
            self.assertEqual(report["window_end_utc"], "2022-10-17T04:00:00+00:00")
            with (output / "comentarios_pos_publicacao.csv").open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(rows[0]["comment_id"], "c1")
            self.assertFalse((output / "chat_ao_vivo.csv").exists())


if __name__ == "__main__":
    unittest.main()
