import os
import urllib.request
import time

from app.api.scryfall_client import ScryfallClient

TWELVE_HOURS = 43200


# Downloads user a bulk card data in form of json. Checks if download
# has happened in recent 12 hours as scryfall api updates bulk card data
# every 12 hours. Avoids getting ip banned due to rate limits/saves user bandwidth
def download_default_cards():
    file_path = "data/default_cards.json"
    if os.path.exists(file_path):
        lastDownload = os.path.getmtime(file_path)  # fetches time file updated/last downloaded
        now = time.time()
        if now - lastDownload < TWELVE_HOURS:
            print('Latest download detected, SKIPPING download')
            return

    client = ScryfallClient()
    bulk_data = client.get_json_data()
    datasets = bulk_data["data"]

    for item in datasets:
        if item["type"] == "default_cards":
            download_url = item["download_uri"]
            os.makedirs("data", exist_ok=True)
            urllib.request.urlretrieve(download_url, "data/default_cards.json")
            print("Download complete")
            break
