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

from app.gui.deck_panel import DeckPanel
from app.gui.detail_panel import DetailPanel
from app.gui.login_window import LoginWindow
from app.gui.search_panel import SearchPanel
from app.gui.theme import apply_theme

POLL_MS = 100
INITIAL_SASH = 660
MOON = "\U0001F319"  # shown in light mode: click to switch to dark
SUN = "☀"       # shown in dark mode: click to switch to light


class MagicSearchApp:

    # takes a factory for the cards rather than a repository so the window can
    # render and report progress while the dataset is still loading
    def __init__(self, load_repository, user_repository, deck_repository, session,
                 title="Scryfall Card Search"):
        self._load_repository = load_repository
        self._users = user_repository
        self._deck_repo = deck_repository
        self._session = session
        self._repository = None
        self._events = queue.Queue()
        self._loading_started = False
        self._dark_mode = False

        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("1000x620")
        self.root.minsize(820, 460)
        self.root.withdraw()  # revealed once the gate is passed
        self._build()

    def _build(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_bar = ttk.Frame(self.root)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.columnconfigure(0, weight=1)
        self.theme_button = ttk.Button(top_bar, text=MOON, width=3, command=self._toggle_theme)
        self.theme_button.grid(row=0, column=1, sticky="e", padx=6, pady=4)

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=1, column=0, sticky="nsew")
        notebook.add(self._build_cards_tab(notebook), text="Card Search")
        notebook.add(self._build_decks_tab(notebook), text="Decks")

        bar = ttk.Frame(self.root)
        bar.grid(row=2, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        self.status = tk.StringVar(value="Loading cards…")
        ttk.Label(bar, textvariable=self.status, relief="sunken",
                  anchor="w", padding=(6, 3)).grid(row=0, column=0, sticky="ew")

        self.identity = tk.StringVar(value="")
        ttk.Label(bar, textvariable=self.identity, padding=(10, 3)).grid(row=0, column=1)
        ttk.Button(bar, text="Sign out", command=self._sign_out).grid(row=0, column=2, padx=(0, 4))

        self._apply_theme()

    def _build_cards_tab(self, parent):
        panes = ttk.PanedWindow(parent, orient="horizontal")
        self.search_panel = SearchPanel(panes, on_search=self._search, on_select=self._select)
        self.detail_panel = DetailPanel(panes, on_add_to_deck=self._add_to_deck)
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

    def _apply_theme(self):
        colors = apply_theme(self.root, self._dark_mode)
        self.detail_panel.apply_theme(colors)
        self.deck_detail_panel.apply_theme(colors)
        self.theme_button.configure(text=SUN if self._dark_mode else MOON)

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self._apply_theme()

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

    # -- decks -------------------------------------------------------------
    # every deck call passes the signed-in user's id and the repository checks
    # it, so neither panel ever decides whose decks it is showing

    # same split as the card tab, so a card in a deck can be inspected without
    # leaving the tab
    def _build_decks_tab(self, parent):
        panes = ttk.PanedWindow(parent, orient="horizontal")
        self.deck_panel = DeckPanel(
            panes,
            on_list=lambda: self._deck_repo.decks_for(self._user_id()),
            on_create=self._create_deck,
            on_delete=self._delete_deck,
            on_cards=lambda deck_id: self._deck_repo.cards_in(self._user_id(), deck_id),
            on_remove=self._remove_from_deck,
            on_select=self._select_deck_card,
            on_set_format=self._set_deck_format,
        )
        self.deck_detail_panel = DetailPanel(panes, on_add_to_deck=self._add_to_deck)
        panes.add(self.deck_panel, weight=4)
        panes.add(self.deck_detail_panel, weight=1)
        return panes

    # deck rows hold only an oracle_id, so the full card comes from the
    # repository, which is not there until the dataset finishes loading
    def _select_deck_card(self, oracle_id):
        if self._repository is None:
            self.status.set("Cards are still loading, try again in a moment")
            return
        card = self._repository.find(oracle_id)
        if card is None:
            self.status.set("That card is no longer in the card data")
            return
        self.deck_detail_panel.show(card)

    def _user_id(self):
        return self._session.user.user_id

    # both the deck tab and the card pane's deck picker show deck data, so
    # any change refreshes the two together
    def _refresh_decks(self):
        self.deck_panel.refresh()
        decks = self._deck_repo.decks_for(self._user_id())
        self.detail_panel.set_decks(decks)
        self.deck_detail_panel.set_decks(decks)

    def _create_deck(self, name):
        deck = self._deck_repo.create(self._user_id(), name)
        self._refresh_decks()
        return deck

    def _delete_deck(self, deck_id):
        self._deck_repo.delete(self._user_id(), deck_id)
        self._refresh_decks()

    def _remove_from_deck(self, deck_id, oracle_id):
        self._deck_repo.remove_card(self._user_id(), deck_id, oracle_id)
        self._refresh_decks()

    def _set_deck_format(self, deck_id, format_key):
        self._deck_repo.set_format(self._user_id(), deck_id, format_key)
        self._refresh_decks()

    def _add_to_deck(self, deck, card):
        try:
            self._deck_repo.add_card(self._user_id(), deck.deck_id, card)
        except ValueError as exc:
            self.status.set(str(exc))
            return
        self._refresh_decks()
        self.status.set(f"Added {card.name} to {deck.name}")

    # -- sign in -----------------------------------------------------------

    def _require_login(self):
        gate = LoginWindow(self.root, self._session, on_create=self._users.create)
        self.root.wait_window(gate)
        return self._session.is_authenticated()

    # runs after every successful sign in, so a second user never sees the
    # previous user's decks
    def _on_signed_in(self):
        self.identity.set(f"Signed in as {self._session.label()}")
        self._refresh_decks()

    def _sign_out(self):
        self._session.logout()
        self.root.withdraw()
        if self._require_login():
            self._on_signed_in()
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
        self._on_signed_in()
        self._show_window()
        self._load_in_background()
        self.root.mainloop()
