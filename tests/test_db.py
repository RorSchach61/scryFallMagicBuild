import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from app.db.connection import connect


class ConnectTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "magic.db"
        with connect(self.path) as conn:
            conn.execute("CREATE TABLE parents (id INTEGER PRIMARY KEY)")
            conn.execute("""CREATE TABLE children (
                id INTEGER PRIMARY KEY,
                parent_id INTEGER NOT NULL REFERENCES parents(id) ON DELETE CASCADE)""")

    def count(self, table):
        with connect(self.path) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_commits_when_the_block_finishes(self):
        with connect(self.path) as conn:
            conn.execute("INSERT INTO parents (id) VALUES (1)")
        self.assertEqual(self.count("parents"), 1)

    def test_rolls_back_when_the_block_raises(self):
        with self.assertRaises(ValueError):
            with connect(self.path) as conn:
                conn.execute("INSERT INTO parents (id) VALUES (1)")
                raise ValueError("something went wrong")
        self.assertEqual(self.count("parents"), 0)

    def test_the_error_still_reaches_the_caller(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with connect(self.path) as conn:
                conn.execute("INSERT INTO parents (id) VALUES (1)")
                conn.execute("INSERT INTO parents (id) VALUES (1)")

    def test_closes_the_connection(self):
        with connect(self.path) as conn:
            pass
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_closes_the_connection_after_an_error(self):
        with self.assertRaises(ValueError):
            with connect(self.path) as conn:
                raise ValueError("something went wrong")
        with self.assertRaises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_foreign_keys_are_on(self):
        with connect(self.path) as conn:
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_cascade_runs(self):
        with connect(self.path) as conn:
            conn.execute("INSERT INTO parents (id) VALUES (1)")
            conn.execute("INSERT INTO children (parent_id) VALUES (1)")
        with connect(self.path) as conn:
            conn.execute("DELETE FROM parents WHERE id = 1")
        self.assertEqual(self.count("children"), 0)

    def test_rows_can_be_read_by_column_name(self):
        with connect(self.path) as conn:
            conn.execute("INSERT INTO parents (id) VALUES (7)")
            self.assertEqual(conn.execute("SELECT id FROM parents").fetchone()["id"], 7)

    def test_works_from_another_thread(self):
        # the reason this helper exists: a shared connection would refuse this
        errors = []

        def work():
            try:
                with connect(self.path) as conn:
                    conn.execute("INSERT INTO parents (id) VALUES (1)")
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=work)
        thread.start()
        thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.count("parents"), 1)


if __name__ == "__main__":
    unittest.main()
