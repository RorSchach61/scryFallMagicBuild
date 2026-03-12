import json
from functools import reduce

from app.models.card import Card


# https://www.100daysofdata.com/python-json
# https://stackoverflow.com/questions/7771011/how-can-i-parse-read-and-use-json-in-python
# parses json, creates python dictionary for creating cards

class searchTools:
    @staticmethod
    def returnName(searchList):
        return searchList


class cardSearch:

    # scryfall json uses non ascii so utf-8 is needed to read those characters
    @staticmethod
    def parseJson():
        file_name = "data/default_cards.json"
        with open(file_name, 'r', encoding="utf-8") as f:
            data = json.load(f)
        return data

    # time complexity O(n) creation time, fetches any card which contains name, will be updated later to
    # be more abstract and accept numerous search input
    @staticmethod
    def searchCard(jsonData, name):
        cardList = filter(lambda x: name.lower().strip() in x["name"].lower().strip().split(), jsonData)
        seen = set()
        searchDict = {}
        i = 1
        for card in cardList:
            if card["name"] not in seen:
                seen.add(card["name"])
                searchDict[card["name"]] = card
        searchDict = sorted(searchDict, key=None)
        for card in searchDict:
            print(card)
