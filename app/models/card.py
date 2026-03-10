# Card class, takes dictionary of card data to create card, can also
# make blank cards, most used by other funct in program
class Card:
    def __init__(self, name, mana_cost, type_line, multiverse_ids, power, toughness, colors, color_identity):
        self.name = name
        self.mana_cost = mana_cost
        self.type_line = type_line
        self.multiverse_ids = multiverse_ids
        self.power = power
        self.toughness = toughness
        self.colors = colors
        self.color_identity = color_identity

    @staticmethod
    def blank_Card():
        return Card("", "", "",
                    [], None, None,
                    [], [])

    # creates card object from scryfall json, is passed dictionary from list in services(card_creator)
    # need to update card creator to pass this function a dictionary
    @staticmethod
    def create_from_json(jsonData):
        return Card(
            jsonData.get("name"), jsonData.get("mana_cost"),
            jsonData.get("type_line"), jsonData.get("multiverse_ids"),
            jsonData.get("power"), jsonData.get("toughness"), jsonData.get("colors"),
            jsonData.get("color_identity")
        )
