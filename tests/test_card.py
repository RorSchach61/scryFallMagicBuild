import unittest

from app.models.card import Card

NORMAL = {
    "name": "Forest Bear",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "multiverse_ids": [1234],
    "power": "2",
    "toughness": "2",
    "colors": ["G"],
    "color_identity": ["G"],
}

# transform cards keep cost, power and colors on the faces, not the top level
DOUBLE_FACED = {
    "name": "Delver of Secrets // Insectile Aberration",
    "type_line": "Creature — Human Insect // Creature — Human Insect",
    "multiverse_ids": [5678],
    "color_identity": ["U"],
    "card_faces": [
        {"name": "Delver of Secrets", "mana_cost": "{U}", "power": "1",
         "toughness": "1", "colors": ["U"]},
        {"name": "Insectile Aberration", "mana_cost": "", "power": "3",
         "toughness": "2", "colors": ["U"]},
    ],
}


class CreateFromJsonTest(unittest.TestCase):

    def test_reads_top_level_fields(self):
        card = Card.create_from_json(NORMAL)
        self.assertEqual(card.name, "Forest Bear")
        self.assertEqual(card.mana_cost, "{1}{G}")
        self.assertEqual(card.power, "2")
        self.assertEqual(card.colors, ["G"])

    def test_falls_back_to_the_front_face(self):
        card = Card.create_from_json(DOUBLE_FACED)
        self.assertEqual(card.mana_cost, "{U}")
        self.assertEqual(card.power, "1")
        self.assertEqual(card.toughness, "1")
        self.assertEqual(card.colors, ["U"])

    def test_keeps_the_combined_name(self):
        card = Card.create_from_json(DOUBLE_FACED)
        self.assertEqual(card.name, "Delver of Secrets // Insectile Aberration")

    def test_empty_mana_cost_is_not_replaced_by_a_face(self):
        # a basic land genuinely costs nothing; "" must survive as ""
        raw = {"name": "Forest", "mana_cost": "", "card_faces": [{"mana_cost": "{G}"}]}
        self.assertEqual(Card.create_from_json(raw).mana_cost, "")

    def test_missing_fields_become_none(self):
        card = Card.create_from_json({"name": "Ancestral Recall"})
        self.assertIsNone(card.mana_cost)
        self.assertIsNone(card.power)

    def test_prefers_png_image(self):
        raw = {"name": "Forest", "image_uris": {"png": "png-url", "normal": "jpg-url"}}
        self.assertEqual(Card.create_from_json(raw).image_url, "png-url")

    def test_falls_back_to_normal_when_png_missing(self):
        raw = {"name": "Forest", "image_uris": {"normal": "jpg-url"}}
        self.assertEqual(Card.create_from_json(raw).image_url, "jpg-url")

    def test_double_faced_image_comes_from_the_front_face(self):
        raw = dict(DOUBLE_FACED)
        raw["card_faces"] = [
            dict(DOUBLE_FACED["card_faces"][0], image_uris={"png": "front-url"}),
            dict(DOUBLE_FACED["card_faces"][1], image_uris={"png": "back-url"}),
        ]
        self.assertEqual(Card.create_from_json(raw).image_url, "front-url")

    def test_no_image_uris_gives_none(self):
        card = Card.create_from_json({"name": "No Art"})
        self.assertIsNone(card.image_url)

    def test_reads_oracle_id(self):
        card = Card.create_from_json({"name": "Forest", "oracle_id": "abc-123"})
        self.assertEqual(card.oracle_id, "abc-123")

    def test_oracle_id_falls_back_to_the_front_face(self):
        # reversible cards keep their oracle_id on the faces
        raw = {"name": "Reversible", "card_faces": [{"oracle_id": "front-id"}]}
        self.assertEqual(Card.create_from_json(raw).oracle_id, "front-id")

    def test_reads_oracle_text(self):
        raw = {"name": "Lightning Bolt", "oracle_text": "Deal 3 damage."}
        self.assertEqual(Card.create_from_json(raw).oracle_text, "Deal 3 damage.")

    def test_oracle_text_joins_every_face(self):
        # unlike other fields, the back face's text must not be dropped
        raw = {"name": "Fire // Ice", "card_faces": [
            {"oracle_text": "Deal 2 damage."}, {"oracle_text": "Tap a permanent."}]}
        self.assertEqual(Card.create_from_json(raw).oracle_text,
                         "Deal 2 damage.\n//\nTap a permanent.")

    def test_missing_oracle_text_is_none(self):
        self.assertIsNone(Card.create_from_json({"name": "Forest"}).oracle_text)

    def test_reads_legalities(self):
        raw = {"name": "Forest", "legalities": {"modern": "legal"}}
        self.assertEqual(Card.create_from_json(raw).legalities, {"modern": "legal"})

    def test_missing_legalities_is_empty(self):
        self.assertEqual(Card.create_from_json({"name": "Forest"}).legalities, {})


class IsLegalTest(unittest.TestCase):

    def setUp(self):
        self.card = Card.create_from_json({"name": "Mana Crypt", "legalities": {
            "legacy": "legal", "vintage": "restricted",
            "commander": "banned", "standard": "not_legal"}})

    def test_legal_is_legal(self):
        self.assertTrue(self.card.is_legal("legacy"))

    def test_restricted_counts_as_legal(self):
        self.assertTrue(self.card.is_legal("vintage"))

    def test_banned_is_not_legal(self):
        self.assertFalse(self.card.is_legal("commander"))

    def test_not_legal_is_not_legal(self):
        self.assertFalse(self.card.is_legal("standard"))

    def test_unknown_format_is_not_legal(self):
        self.assertFalse(self.card.is_legal("madeup"))

    def test_format_name_is_case_insensitive(self):
        self.assertTrue(self.card.is_legal("Legacy"))

    def test_card_without_data_is_not_legal(self):
        self.assertFalse(Card.create_from_json({"name": "Forest"}).is_legal("modern"))


class PowerToughnessTest(unittest.TestCase):

    def test_creature_shows_both(self):
        self.assertEqual(Card.create_from_json(NORMAL).power_toughness(), "2/2")

    def test_noncreature_shows_nothing(self):
        card = Card.create_from_json({"name": "Lightning Bolt", "type_line": "Instant"})
        self.assertEqual(card.power_toughness(), "")

    def test_zero_power_is_still_shown(self):
        card = Card.create_from_json(
            {"name": "Wall", "power": "0", "toughness": "4"}
        )
        self.assertEqual(card.power_toughness(), "0/4")


class BlankCardTest(unittest.TestCase):

    def test_has_empty_fields(self):
        card = Card.blank_Card()
        self.assertEqual(card.name, "")
        self.assertEqual(card.multiverse_ids, [])
        self.assertIsNone(card.power)


if __name__ == "__main__":
    unittest.main()
