import http.client
import urllib.parse
import time
import json


class ScryfallClient:

    def __init__(self):
        self.host = "api.scryfall.com"
        self.headers = {
            "User-Agent": "scryFallMagicBuild/0.1",
            "Accept": "application/json"
        }

    # Grabs list of bulk data files
    def get_json_data(self):
        time.sleep(0.1)
        conn = http.client.HTTPSConnection(self.host)
        conn.request("GET", "/bulk-data", headers=self.headers)

        response = conn.getresponse()
        data = response.read()

        return json.loads(data)

