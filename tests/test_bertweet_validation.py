import unittest

from analise_sentimentos.pipelines.bertweet_validation import check_prediction, language_features
from analise_sentimentos.pipelines.social_preprocessing import preprocess_social_text
from analise_sentimentos.pipelines.transformer_attribution import attribute_to_candidates


def prediction(text="Lula foi muito bem 👏"):
    p = {"NEG": 0.02, "NEU": 0.03, "POS": 0.95}
    from analise_sentimentos.pipelines.band_blocks import MODEL_ID, MODEL_REVISION
    return {"texto_classificado": text, "texto_entrada_modelo": preprocess_social_text(text),
            "prob_negativo": "0.02", "prob_neutro": "0.03", "prob_positivo": "0.95",
            "sentimento_geral_automatico": "positivo", "confianca_modelo": "0.95",
            "modelo_id": MODEL_ID, "modelo_revisao": MODEL_REVISION,
            "truncado_128": "0", "tokens_antes_corte": "12", **attribute_to_candidates(text, p)}


class BertweetValidationTests(unittest.TestCase):
    def test_valid_prediction_and_emoji_input(self):
        self.assertEqual(check_prediction(prediction()), [])
        self.assertIn("emoji", prediction()["texto_entrada_modelo"])

    def test_corrupt_probabilities_are_rejected(self):
        for value in ("nan", "inf", "-0.1", "1.2"):
            with self.subTest(value=value):
                row = prediction()
                row["prob_positivo"] = value
                self.assertIn("probabilidade_invalida", check_prediction(row))
        row = prediction()
        row["prob_neutro"] = "0.5"
        self.assertIn("soma_probabilidades", check_prediction(row))

    def test_target_transfer_and_preprocessing_corruption_are_detected(self):
        row = prediction("Lula foi bem e Flávio foi mal")
        row["sentimento_lula_automatico"] = "positivo"
        row["texto_entrada_modelo"] = "outro texto"
        issues = check_prediction(row)
        self.assertIn("atribuicao_candidato", issues)
        self.assertIn("preprocessamento", issues)

    def test_irony_cues_do_not_become_a_classifier_label(self):
        features = language_features("Lula foi ótimo, só que não 🙄")
        self.assertEqual(features["emojis"], ["🙄"])
        self.assertIn("só que não", features["irony_cues"])
        self.assertNotIn("ironic", features)
        self.assertEqual(language_features("Lula falou ❤️")["irony_cues"], [])


if __name__ == "__main__":
    unittest.main()
