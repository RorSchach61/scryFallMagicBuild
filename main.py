"""Entry point. Assembles the pieces and hands them to the window."""
from app.gui.app import MagicSearchApp
from app.services.card_repository import InMemoryCardRepository
from app.services.deck_repository import SqliteDeckRepository
from app.services.json_downloader import download_oracle_cards
from app.services.session import Session
from app.services.user_repository import SqliteUserRepository


# runs on the window's loading thread, so a slow download never delays the window.
# returns the download's outcome alongside the cards so the window can show it
def load_cards(progress=None, report=None, force=False):
    result = download_oracle_cards(force=force, report=report)
    return InMemoryCardRepository.load(progress), result


def main():
    users = SqliteUserRepository()  # first: the decks table references users
    MagicSearchApp(
        load_repository=load_cards,
        user_repository=users,
        deck_repository=SqliteDeckRepository(),
        session=Session(users),
    ).run()


if __name__ == "__main__":
    main()
