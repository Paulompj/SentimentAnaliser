"""Protege o layout do pacote e a separação das duas classificações."""

import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analise_sentimentos.pipelines.transformer_chat import load_rows, main as transformer_main
from scripts import classificar_chat_globo


class PipelineLayoutTests(unittest.TestCase):
    def test_application_code_lives_in_one_package(self):
        root = Path(__file__).resolve().parents[1]
        package = root / "analise_sentimentos"
        self.assertTrue(all((package / name).is_dir() for name in
                            ("domain", "sources", "pipelines", "config", "web")))
        self.assertFalse(any((root / name).exists() for name in
                             ("analysis", "youtube", "pipelines", "config", "frontend", "sentimento")))

    def test_globo_entry_point_uses_its_own_files(self):
        with patch.object(classificar_chat_globo, "classify_chat") as classify:
            classificar_chat_globo.main(["--lote", "8"])
        self.assertEqual(classify.call_args.args, (["--lote", "8"],))
        self.assertEqual(classify.call_args.kwargs["debate"], "Globo 2026")
        self.assertEqual(classify.call_args.kwargs["default_input"].name,
                         "rotulacao_chat_globo.csv")
        self.assertEqual(classify.call_args.kwargs["default_output"].name,
                         "rotulacao_automatica_chat_globo.csv")

    def test_transformer_never_uses_manual_file_as_destination(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            source = Path(folder) / "rotulacao.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "message_id", "video_id", "published_at", "bloco", "text"])
                writer.writeheader()
                writer.writerow({"message_id": "1", "video_id": "video",
                                 "published_at": "2026-01-01T00:00:00Z", "bloco": "1",
                                 "text": "Comentário"})
            original = source.read_bytes()
            self.assertEqual(len(load_rows(source)), 1)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    transformer_main(["--entrada", str(source), "--saida", str(source)])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
