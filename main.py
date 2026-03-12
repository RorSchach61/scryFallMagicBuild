from app.services.json_downloader import download_default_cards
from app.services.searchCards import cardSearch
#download_default_cards()

cardSearch.searchCard(cardSearch().parseJson(),"Forest")
