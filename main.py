"""Entry point. Assembles the pieces and hands them to the window."""
from app.gui.app import MagicSearchApp
from app.repositories.card_repository import InMemoryCardRepository
from app.repositories.deck_repository import SqliteDeckRepository
from app.repositories.user_repository import SqliteUserRepository
from app.services.json_downloader import download_oracle_cards
from app.services.session import Session
from app.utils.error_log import setup_logging


# runs on the window's loading thread, so a slow download never delays the window.
# returns the download's outcome alongside the cards so the window can show it
def load_cards(progress=None, report=None, force=False):
    result = download_oracle_cards(force=force, report=report)
    return InMemoryCardRepository.load(progress), result


def main():
    setup_logging()  # first, so anything that fails below can be recorded
    users = SqliteUserRepository()  # first: the decks table references users
    MagicSearchApp(
        load_repository=load_cards,
        user_repository=users,
        deck_repository=SqliteDeckRepository(),
        session=Session(users),
    ).run()


if __name__ == "__main__":
    main()
