from app.services.json_downloader import download_default_cards
from app.services.card_Creator import cardForge
#download_default_cards()

cardForge.createCard(cardForge().parseJson(),"Forest")