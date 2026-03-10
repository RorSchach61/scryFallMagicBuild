import json
from app.models.card import Card


# https://www.100daysofdata.com/python-json
# https://stackoverflow.com/questions/7771011/how-can-i-parse-read-and-use-json-in-python
# parses json, creates python dictionary for creating cards

class cardForge:

    # scryfall json uses non ascii so utf-8 is needed to read those characters
    @staticmethod
    def parseJson():
        file_name = "data/default_cards.json"
        with open(file_name, 'r', encoding="utf-8") as f:
            data = json.load(f)
        return data

    @staticmethod
    def createCard(jsonData, name):
        cardList = list(filter(lambda x: name.lower() in x["name"].lower(), jsonData))
        deck = []
        for card in cardList:
            deck.append(Card.create_from_json(card))
        for card in deck:
            print(card.name)