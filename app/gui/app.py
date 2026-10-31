"""Main window.

Wires the panels to their repositories. The card repository is built on a worker
thread because parsing the dataset takes seconds and would otherwise freeze the
window; results come back through a queue since tk widgets may only be touched
from the thread that created them.

The window stays hidden until the sign-in gate succeeds, and hides again on
sign out rather than tearing down, so the loaded dataset survives.
"""
import math
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from app.config import LOG_PATH
from app.gui.account_window import AccountWindow
from app.gui.deck_panel import DeckPanel
from app.gui.detail_panel import DetailPanel
from app.gui.login_window import LoginWindow
from app.gui.search_panel import SearchPanel
from app.gui.theme import apply_theme
from app.services.deck_rules import illegal_entries
from app.services.json_downloader import cooldown_remaining
from app.utils.error_log import log_error

POLL_MS = 100
INITIAL_SASH = 660
MOON = "\U0001F319"  # shown in light mode: click to switch to dark
SUN = "☀"       # shown in dark mode: click to switch to light
DATA_NOTE = "Card data comes from Scryfall and updates about once a day."


# for failures before the window exists, so it builds its own hidden root
def show_startup_error():
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Scryfall Card Search could not start",
        f"Details were saved to:\n{LOG_PATH}",
        parent=root,
    )
    root.destroy()


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
        self._loading = False
        self._last_refresh = None  # when the refresh button last started a download
        self._dark_mode = False

        self.root = tk.Tk()
        self.root.report_callback_exception = self._on_callback_error
        self.root.title(title)
        self.root.geometry("1000x620")
        self.root.minsize(820, 460)
        self.root.withdraw()  # revealed once the gate is passed
        self._build()

    # tk calls this for any error a button or window callback did not handle,
    # in every window. the default prints to a console the .exe does not have,
    # which would make a failed action look like an ignored click
    def _on_callback_error(self, _exc_type, error, _traceback):
        log_error("Unhandled error in the window", error)
        messagebox.showerror(
            "Something went wrong",
            f"That action did not finish.\nDetails were saved to:\n{LOG_PATH}",
            parent=self.root,
        )

    def _build(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top_bar = ttk.Frame(self.root)
        top_bar.grid(row=0, column=0, sticky="ew")
        top_bar.columnconfigure(1, weight=1)
        self.refresh_button = ttk.Button(top_bar, text="Refresh card data",
                                         command=self._refresh_cards, state="disabled")
        self.refresh_button.grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Label(top_bar, text=DATA_NOTE).grid(row=0, column=1, sticky="w")
        self.theme_button = ttk.Button(top_bar, text=MOON, width=3, command=self._toggle_theme)
        self.theme_button.grid(row=0, column=2, sticky="e", padx=6, pady=4)

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
        ttk.Button(bar, text="Edit account", command=self._edit_account).grid(
            row=0, column=2, padx=(0, 4))
        ttk.Button(bar, text="Sign out", command=self._sign_out).grid(row=0, column=3, padx=(0, 4))

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
            on_check=self._check_deck,
        )
        self.deck_detail_panel = DetailPanel(panes, on_add_to_deck=self._add_to_deck)
        panes.add(self.deck_panel, weight=4)
        panes.add(self.deck_detail_panel, weight=1)
        panes.bind("<Map>", lambda _event: self._place_deck_sash(panes))
        return panes

    # the decks tab is hidden at startup, so like the card tab its sash can only
    # be placed once it has a real size: here, the first time the tab is shown
    def _place_deck_sash(self, panes):
        panes.unbind("<Map>")
        self.root.after(50, lambda: self._place_sash(panes))

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

    def _check_deck(self, format_key, entries):
        if self._repository is None:
            return None
        return illegal_entries(format_key, entries, self._repository.find)

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
        self._show_identity()
        self._refresh_decks()

    def _show_identity(self):
        self.identity.set(f"Signed in as {self._session.label()}")

    def _sign_out(self):
        self._session.logout()
        self.root.withdraw()
        if self._require_login():
            self._on_signed_in()
            self._show_window()
        else:
            self.root.destroy()

    # -- account -----------------------------------------------------------

    def _edit_account(self):
        AccountWindow(self.root, self._session.user, on_save=self._save_account,
                      on_check_password=self._check_password, on_delete=self._delete_account)

    def _save_account(self, username, display_name):
        user = self._users.update(self._user_id(), username, display_name)
        self._show_identity()
        return user

    def _check_password(self, password):
        return self._users.authenticate(self._session.user.username, password) is not None

    # signing out straight away hides the window, so no deck action can run
    # with a user that no longer exists
    def _delete_account(self):
        self._users.delete(self._user_id())
        self._sign_out()

    # -- dataset loading ---------------------------------------------------

    # force downloads a new copy regardless of age; used by the refresh button
    def _load_in_background(self, force=False):
        if self._loading:
            return
        self._loading = True
        self.refresh_button.configure(state="disabled")

        def work():
            try:
                loaded = self._load_repository(
                    progress=lambda n: self._events.put(("progress", n)),
                    report=lambda message: self._events.put(("status", message)),
                    force=force,
                )
                self._events.put(("ready", loaded))
            except Exception as exc:  # surfaced in the status bar
                log_error("Could not load cards", exc)
                self._events.put(("error", exc))

        threading.Thread(target=work, daemon=True).start()

    # the cooldown keeps repeated clicks from downloading the full file again
    # and again; scryfall only publishes new data about once a day anyway
    def _refresh_cards(self):
        remaining = cooldown_remaining(self._last_refresh)
        if remaining:
            self.status.set(f"Card data was just refreshed, try again in "
                            f"{math.ceil(remaining / 60)} min")
            return
        self._last_refresh = time.time()
        self.status.set("Checking Scryfall for card data…")
        self._load_in_background(force=True)

    def _drain_events(self):
        try:
            while True:
                kind, payload = self._events.get_nowait()
                if kind == "progress":
                    self.status.set(f"Loading cards… {payload:,} parsed")
                elif kind == "status":
                    self.status.set(payload)
                elif kind == "ready":
                    repository, download = payload
                    self._repository = repository
                    self._loading = False
                    self.refresh_button.configure(state="normal")
                    # re-run whatever is in the search box against the new
                    # cards, which also covers anything typed while loading
                    self.search_panel.refresh()
                    loaded = f"{repository.count():,} cards loaded"
                    self.status.set(f"{loaded}. {download.message}" if download.message else loaded)
                    self.search_panel.focus_entry()
                    # the legality column is blank until card data exists, and
                    # loading can finish while the user is signed out
                    if self._session.is_authenticated():
                        self.deck_panel.refresh()
                elif kind == "error":
                    self._loading = False
                    self.refresh_button.configure(state="normal")
                    self.status.set(f"Could not load cards: {payload}")
        except queue.Empty:
            pass
        finally:
            # in finally so one failed event cannot stop polling for good. the
            # error itself carries on to the window's error handler
            self.root.after(POLL_MS, self._drain_events)

    def run(self):
        if not self._require_login():
            self.root.destroy()  # gate dismissed, nothing to show
            return
        self._on_signed_in()
        self._show_window()
        self.root.after(POLL_MS, self._drain_events)
        self._load_in_background()
        self.root.mainloop()
