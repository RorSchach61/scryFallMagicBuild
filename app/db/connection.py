"""Opens SQLite connections, the same way everywhere.

Each call gets its own short-lived connection, so threads never share one. This
is the only place that connects, so no connection can miss the settings below.
"""
import sqlite3
from contextlib import contextmanager


# commits when the block finishes and rolls back if it raises, so callers never
# commit by hand. the connection is closed either way; `with conn` alone does not
@contextmanager
def connect(path):
    conn = sqlite3.connect(str(path))
    try:
        conn.row_factory = sqlite3.Row
        # sqlite ignores REFERENCES unless this is switched on, per connection
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            yield conn
    finally:
        conn.close()
