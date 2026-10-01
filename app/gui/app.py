"""Main window.

Wires the panels to their repositories. The card repository is built on a worker
thread because parsing the dataset takes seconds and would otherwise freeze the
window; results come back through a queue since tk widgets may only be touched
from the thread that created them.

The window stays hidden until the sign-in gate succeeds, and hides again on
sign out rather than tearing down, so the loaded dataset survives.
"""
import queue
import threading
import tkinter as tk
from tkinter import ttk

from app.gui.detail_panel import DetailPanel
from app.gui.login_window import LoginWindow
from app.gui.search_panel import SearchPanel
from app.gui.user_panel import UserPanel

POLL_MS = 100
INITIAL_SASH = 660


class MagicSearchApp:

    # takes a factory for the cards rather than a repository so the window can
    # render and report progress while the dataset is still loading
    def __init__(self, load_repository, user_repository, session,
                 title="Scryfall Card Search"):
        self._load_repository = load_repository
        self._users = user_repository
        self._session = session
        self._repository = None
        self._events = queue.Queue()
        self._loading_started = False

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("1000x620")
        self.root.minsize(820, 460)
        self.root.withdraw()  # revealed once the gate is passed
        self._build()

    def _build(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky="nsew")
        notebook.add(self._build_cards_tab(notebook), text="Card Search")
        notebook.add(self._build_users_tab(notebook), text="Users")

        bar = ttk.Frame(self.root)
        bar.grid(row=1, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        self.status = tk.StringVar(value="Loading cards…")
        ttk.Label(bar, textvariable=self.status, relief="sunken",
                  anchor="w", padding=(6, 3)).grid(row=0, column=0, sticky="ew")

        self.identity = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.identity, padding=(10, 3)).grid(row=0, column=1)
        ttk.Button(bar, text="Sign out", command=self._sign_out).grid(row=0, column=2, padx=(0, 4))

    def _build_cards_tab(self, parent):
        panes = ttk.PanedWindow(parent, orient="horizontal")
        self.search_panel = SearchPanel(panes, on_search=self._search, on_select=self._select)
        self.detail_panel = DetailPanel(panes)
        panes.add(self.search_panel, weight=4)
        panes.add(self.detail_panel, weight=1)
        self._card_panes = panes
        return panes

    # must run after deiconify(), not at construction time: the window is
    # withdrawn until sign-in succeeds, and winfo_width() on a withdrawn,
    # never-yet-shown window returns 1, not its real size. Placing the sash
    # off that bogus width drives it negative and the search pane collapses
    # to nothing, which is exactly what a too-early call here caused before.
    def _show_window(self):
        self.root.deiconify()
        self.root.after(50, lambda: self._place_sash(self._card_panes))

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

    # -- sign in -----------------------------------------------------------

    def _require_login(self):
        gate = LoginWindow(self.root, self._session, on_create=self._users.create)
        self.root.wait_window(gate)
        return self._session.is_authenticated()

    def _show_identity(self):
        self.identity.set(f"Signed in as {self._session.label()}")

    def _sign_out(self):
        self._session.logout()
        self.root.withdraw()
        if self._require_login():
            self._show_identity()
            self.user_panel.refresh()
            self._show_window()
        else:
            self.root.destroy()

    # -- dataset loading ---------------------------------------------------

    def _load_in_background(self):
        if self._loading_started:
            return
        self._loading_started = True

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
        if not self._require_login():
            self.root.destroy()  # gate dismissed, nothing to show
            return
        self._show_identity()
        self._show_window()
        self._load_in_background()
        self.root.mainloop()
