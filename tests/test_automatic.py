import unittest

from analise_sentimentos.pipelines.transformer_attribution import attribute_to_candidates


P = {"NEG": 0.91, "NEU": 0.05, "POS": 0.04}


class AttributionTests(unittest.TestCase):
    def test_single_explicit_candidate(self):
        result = attribute_to_candidates("Flávio é horrível", P)
        self.assertEqual(result["sentimento_flavio_automatico"], "negativo")
        self.assertEqual(result["sentimento_lula_automatico"], "sem_referencia")

    def test_two_candidates_cannot_share_whole_text_polarity(self):
        result = attribute_to_candidates("Lula é horrível, Flávio é ótimo", P)
        self.assertEqual(result["sentimento_lula_automatico"], "incerto")
        self.assertEqual(result["sentimento_flavio_automatico"], "incerto")

    def test_surname_or_election_number_is_ambiguous(self):
        self.assertEqual(attribute_to_candidates("22", P)["sentimento_flavio_automatico"],
                         "incerto")
        self.assertEqual(attribute_to_candidates("Bolsonaro", P)["sentimento_flavio_automatico"],
                         "incerto")

    def test_jair_is_not_flavio(self):
        result = attribute_to_candidates("Jair Bolsonaro fala", P)
        self.assertEqual(result["sentimento_flavio_automatico"], "sem_referencia")

    def test_other_politician_blocks_whole_text_attribution(self):
        result = attribute_to_candidates("Jair Bolsonaro é horrível. Lula chegou", P)
        self.assertEqual(result["sentimento_lula_automatico"], "incerto")

    def test_keycap_numbers_stay_ambiguous(self):
        result = attribute_to_candidates("2️⃣2️⃣", P)
        self.assertEqual(result["sentimento_flavio_automatico"], "incerto")

    def test_low_probability_is_uncertain(self):
        result = attribute_to_candidates("Lula fala", {"NEG": 0.40, "NEU": 0.35, "POS": 0.25})
        self.assertEqual(result["sentimento_lula_automatico"], "incerto")


if __name__ == "__main__":
    unittest.main()
