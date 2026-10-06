# Card class, takes dictionary of card data to create card, can also
# make blank cards, most used by other funct in program
class Card:
    def __init__(self, name, mana_cost, type_line, multiverse_ids, power, toughness,
                 colors, color_identity, image_url=None, oracle_id=None):
        self.oracle_id = oracle_id  # scryfall's stable id for the card, used by decks
        self.name = name
        self.mana_cost = mana_cost
        self.type_line = type_line
        self.multiverse_ids = multiverse_ids
        self.power = power
        self.toughness = toughness
        self.colors = colors
        self.color_identity = color_identity
        self.image_url = image_url

    @staticmethod
    def blank_Card():
        return Card("", "", "",
                    [], None, None,
                    [], [])

    # creates card object from scryfall json, is passed dictionary from list in services(card_creator)
    # double faced cards keep mana cost, power and colors on the individual faces
    # rather than the top level, so the front face is used as a fallback
    @staticmethod
    def create_from_json(jsonData):
        faces = jsonData.get("card_faces") or []
        front = faces[0] if faces else {}

        def field(key):
            value = jsonData.get(key)
            return front.get(key) if value is None else value

        image_uris = field("image_uris") or {}
        image_url = image_uris.get("png") or image_uris.get("normal")

        return Card(
            jsonData.get("name"), field("mana_cost"),
            field("type_line"), jsonData.get("multiverse_ids"),
            field("power"), field("toughness"), field("colors"),
            jsonData.get("color_identity"), image_url, field("oracle_id")
        )

    # creatures show power/toughness, everything else has neither
    def power_toughness(self):
        if self.power is None and self.toughness is None:
            return ""
        return f"{self.power}/{self.toughness}"

    def __repr__(self):
        return f"Card({self.name!r})"
