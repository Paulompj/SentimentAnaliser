import unittest

from analise_sentimentos.pipelines.social_preprocessing import preprocess_social_text


class SocialPreprocessingTests(unittest.TestCase):
    def test_hashtag_and_emoji_become_text(self):
        result = preprocess_social_text("#ForaLula 🇧🇷")
        self.assertIn("hashtag fora lula", result)
        self.assertIn("emoji", result)

    def test_repeated_letters_are_shortened(self):
        self.assertEqual(preprocess_social_text("boooom"), "booom")


if __name__ == "__main__":
    unittest.main()
