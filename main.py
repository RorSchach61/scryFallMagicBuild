"""Entry point. Assembles the pieces and hands them to the window."""
from app.gui.app import MagicSearchApp
from app.services.card_repository import InMemoryCardRepository
from app.services.deck_repository import SqliteDeckRepository
from app.services.json_downloader import download_oracle_cards
from app.services.session import Session
from app.services.user_repository import SqliteUserRepository


def main():
    download_oracle_cards()
    users = SqliteUserRepository()  # first: the decks table references users
    MagicSearchApp(
        load_repository=InMemoryCardRepository.load,
        user_repository=users,
        deck_repository=SqliteDeckRepository(),
        session=Session(users),
    ).run()


if __name__ == "__main__":
    main()
