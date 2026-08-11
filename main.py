"""Entry point. Assembles the pieces and hands them to the window."""
from app.gui.app import MagicSearchApp
from app.services.card_repository import InMemoryCardRepository
from app.services.json_downloader import download_oracle_cards
from app.services.user_repository import SqliteUserRepository


def main():
    download_oracle_cards()
    MagicSearchApp(
        load_repository=InMemoryCardRepository.load,
        user_repository=SqliteUserRepository(),
    ).run()


if __name__ == "__main__":
    main()
