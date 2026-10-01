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
