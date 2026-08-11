"""Main window.

Wires the panels to their repositories. The card repository is built on a worker
thread because parsing the dataset takes seconds and would otherwise freeze the
window; results come back through a queue since tk widgets may only be touched
from the thread that created them.
"""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from app.gui.detail_panel import DetailPanel
from app.gui.search_panel import SearchPanel
from app.gui.user_panel import UserPanel

POLL_MS = 100
INITIAL_SASH = 660


class MagicSearchApp:

    # takes a factory for the cards rather than a repository so the window can
    # render and report progress while the dataset is still loading
    def __init__(self, load_repository, user_repository, title="Scryfall Card Search"):
        self._load_repository = load_repository
        self._users = user_repository
        self._repository = None
        self._events = queue.Queue()

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("1000x620")
        self.root.minsize(820, 460)
        self._build()

    def _build(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky="nsew")
        notebook.add(self._build_cards_tab(notebook), text="Card Search")
        notebook.add(self._build_users_tab(notebook), text="Users")

        self.status = tk.StringVar(value="Loading cards…")
        ttk.Label(self.root, textvariable=self.status, relief="sunken",
                  anchor="w", padding=(6, 3)).grid(row=1, column=0, sticky="ew")

    def _build_cards_tab(self, parent):
        panes = ttk.PanedWindow(parent, orient="horizontal")
        self.search_panel = SearchPanel(panes, on_search=self._search, on_select=self._select)
        self.detail_panel = DetailPanel(panes)
        panes.add(self.search_panel, weight=4)
        panes.add(self.detail_panel, weight=1)
        # the sash defaults to the middle, leaving the detail labels clipped,
        # so it is placed once the panes have been given their real size
        self.root.after(50, lambda: self._place_sash(panes))
        return panes

    def _place_sash(self, panes):
        try:
            panes.sashpos(0, min(INITIAL_SASH, self.root.winfo_width() - 260))
        except tk.TclError:
            pass

    def _build_users_tab(self, parent):
        self.user_panel = UserPanel(
            parent, on_create=self._create_user, on_list=self._users.all_users
        )
        return self.user_panel

    def _search(self, term, limit):
        if self._repository is None:
            return []
        results = self._repository.search(term, limit=limit)
        if term.strip():
            self.status.set(f"{len(results)} match(es) for {term.strip()!r}")
        else:
            self.status.set(f"{self._repository.count():,} cards loaded")
        return results

    def _select(self, card):
        self.detail_panel.show(card)

    def _create_user(self, username, display_name, password, confirmation):
        user = self._users.create(username, display_name, password, confirmation)
        self.status.set(f"Created user {user.username!r}")
        return user

    def _load_in_background(self):
        def work():
            try:
                repository = self._load_repository(
                    progress=lambda n: self._events.put(("progress", n))
                )
                self._events.put(("ready", repository))
            except Exception as exc:  # surfaced in the status bar
                self._events.put(("error", exc))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(POLL_MS, self._drain_events)

    def _drain_events(self):
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "progress":
                    self.status.set(f"Loading cards… {payload:,} parsed")
                elif kind == "ready":
                    self._repository = payload
                    self.status.set(f"{payload.count():,} cards loaded")
                    self.search_panel.focus_entry()
                elif kind == "error":
                    self.status.set(f"Could not load cards: {payload}")
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self._drain_events)

    def run(self):
        self._load_in_background()
        self.root.mainloop()
