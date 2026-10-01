## About

A desktop Magic: The Gathering card search built on Scryfall's bulk card data. Cards are parsed once into memory at startup and served from there, rather than re-reading the dataset per search (~2s → ~3ms). Accounts are backed by SQLite with salted, PBKDF2-hashed passwords; search, storage, and the UI are each behind their own interface so any layer can be swapped without touching the others.

**Stack:** Python, Tkinter, SQLite — standard library only, no third-party dependencies.

**Run it:**
```
python main.py
```
