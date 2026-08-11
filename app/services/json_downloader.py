import os
import urllib.request
import time

from app.api.scryfall_client import ScryfallClient
from app.config import BULK_DATASET_TYPE, DATA_DIR, ORACLE_CARDS_PATH, TWELVE_HOURS


# Downloads user a bulk card data in form of json. Checks if download
# has happened in recent 12 hours as scryfall api updates bulk card data
# every 12 hours. Avoids getting ip banned due to rate limits/saves user bandwidth
def download_oracle_cards():
    if ORACLE_CARDS_PATH.exists():
        lastDownload = os.path.getmtime(ORACLE_CARDS_PATH)  # fetches time file updated/last downloaded
        now = time.time()
        if now - lastDownload < TWELVE_HOURS:
            print('Latest download detected, SKIPPING download')
            return

    client = ScryfallClient()
    bulk_data = client.get_json_data()
    datasets = bulk_data["data"]

    # oracle_cards is one entry per unique card, default_cards is one per printing
    for item in datasets:
        if item["type"] == BULK_DATASET_TYPE:
            download_url = item["jsonl_download_uri"]
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(download_url, ORACLE_CARDS_PATH)
            print("Download complete")
            break
