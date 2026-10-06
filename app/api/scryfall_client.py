import http.client
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
        return self._get("/bulk-data")

    def _get(self, path):
        time.sleep(0.1)
        conn = http.client.HTTPSConnection(self.host, timeout=10)
        try:
            conn.request("GET", path, headers=self.headers)
            response = conn.getresponse()
            data = response.read()
        finally:
            conn.close()
        self._check_status(response)
        return json.loads(data)

    @staticmethod
    def _check_status(response):
        if response.status != 200:
            raise OSError(f"Scryfall returned HTTP {response.status}")

