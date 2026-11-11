import csv
import json
import tempfile
import unittest
from pathlib import Path

from analise_sentimentos.pipelines.band_blocks import (
    extract_superchat_comment, load_blocks, open_cache, summarize,
)


class BandBlocksTests(unittest.TestCase):
    def test_superchat_extracts_comment_without_payment_and_author(self):
        self.assertEqual(extract_superchat_comment('R$10.90 from @pessoa: "Bora Lula"'), "Bora Lula")
        self.assertIsNone(extract_superchat_comment('R$1.00 from @pessoa'))
        self.assertIsNone(extract_superchat_comment('Lemon character blowing a heart'))

    def test_block_inventory_reconciles_all_message_types(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            source = Path(folder)
            blocks = []
            for index in range(5):
                name = f"bloco_{index}.csv"
                rows = [{"message_id": f"texto-{index}", "video_id": "video",
                         "published_at": "2026-10-18T23:00:00Z", "message_type": "textMessageEvent",
                         "text": "Bora Lula"}]
                if index == 0:
                    rows.extend([
                        {"message_id": "pago", "video_id": "video",
                         "published_at": "2026-10-18T23:00:01Z", "message_type": "superChatEvent",
                         "text": 'R$2.00 from @pessoa: "Flávio falou"'},
                        {"message_id": "sticker", "video_id": "video",
                         "published_at": "2026-10-18T23:00:02Z", "message_type": "superStickerEvent",
                         "text": "Sticker"},
                    ])
                with (source / name).open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                blocks.append({"name": f"Bloco {index}", "file": name, "messages": len(rows)})
            (source / "resumo_blocos.json").write_text(json.dumps(blocks), encoding="utf-8")
            regular, paid, excluded, manifest = load_blocks(source)
            self.assertEqual((len(regular), len(paid), len(excluded)), (5, 1, 1))
            self.assertEqual(paid[0].text, "Flávio falou")
            self.assertEqual(excluded[0]["motivo"], "sticker_sem_texto_opinativo")
            self.assertEqual(sum(item["registros"] for item in manifest), 7)
            result = summarize(manifest,
                               [{"bloco": message.bloco, "sentimento_geral_automatico": "positivo"}
                                for message in regular],
                               [{"bloco": paid[0].bloco, "sentimento_geral_automatico": "neutro"}],
                               excluded)
            self.assertEqual(result[0]["total_registros"], 3)
            self.assertEqual(result[0]["positivo_texto"], 1)
            self.assertEqual(result[0]["neutro_superchat"], 1)

    def test_checkpoint_refuses_other_source_or_model(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / "checkpoint.sqlite"
            connection = open_cache(path, "fingerprint-a")
            connection.close()
            connection = open_cache(path, "fingerprint-a")
            connection.close()
            with self.assertRaises(ValueError):
                open_cache(path, "fingerprint-b")


if __name__ == "__main__":
    unittest.main()
