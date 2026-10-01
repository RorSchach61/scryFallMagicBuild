"""Read-only view of a single card."""
import queue
import threading
import tkinter as tk
import urllib.request
from tkinter import ttk

FIELDS = (
    ("Mana cost", lambda card: card.mana_cost or "N/A"),
    ("Type", lambda card: card.type_line or "N/A"),
    ("Power/Toughness", lambda card: card.power_toughness() or "N/A"),
    ("Colors", lambda card: ", ".join(card.colors or []) or "Colorless"),
    ("Color identity", lambda card: ", ".join(card.color_identity or []) or "Colorless"),
    ("Multiverse IDs", lambda card: ", ".join(str(i) for i in card.multiverse_ids or []) or "N/A"),
)

# scryfall's png is a full-size card (~745px wide); subsample(3) brings it down
# to roughly the detail pane's wraplength without needing Pillow to resize
IMAGE_SUBSAMPLE = 3
POLL_MS = 60


class DetailPanel(ttk.Frame):

    # a plain Frame can't scroll on its own, so the pane is a Canvas holding
    # an embedded content Frame; everything below used to be built directly
    # on `self` and now builds on that embedded frame instead
    def __init__(self, parent):
        super().__init__(parent)
        self._values = {}
        self._image_cache = {}  # url -> PhotoImage, so revisiting a card is free
        self._image_events = queue.Queue()
        self._request_token = 0
        self._pending_token = None
        self._build_scroll_frame()
        self._build_content()
        self.clear()

    def _build_scroll_frame(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._content = ttk.Frame(self._canvas, padding=(8, 8))
        self._content_window = self._canvas.create_window((0, 0), window=self._content, anchor="nw")

        # scrollregion must track the content's real size, and the embedded
        # window's width must track the canvas's, or content either clips or
        # leaves a stale horizontal gap as the pane is resized
        self._content.bind("<Configure>", lambda _e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(
            self._content_window, width=e.width))

        # wheel scrolling is bound only while the pointer is over this pane,
        # so it doesn't hijack scrolling in the search results next to it
        self._canvas.bind("<Enter>", lambda _e: self._canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self._canvas.bind("<Leave>", lambda _e: self._canvas.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def _build_content(self):
        parent = self._content
        parent.columnconfigure(1, weight=1)

        self.title = ttk.Label(parent, text="", font=("TkDefaultFont", 12, "bold"),
                               wraplength=240, justify="left")
        self.title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # labels stack above their values rather than sitting beside them, so a
        # long type line wraps instead of being clipped by a narrow pane
        for row, (label, _) in enumerate(FIELDS):
            ttk.Label(parent, text=label, foreground="gray35").grid(
                row=row * 2 + 1, column=0, sticky="w", pady=(6, 0))
            value = ttk.Label(parent, text="", wraplength=240, justify="left")
            value.grid(row=row * 2 + 2, column=0, sticky="w")
            self._values[label] = value

        self.image_label = ttk.Label(parent)
        self.image_label.grid(row=len(FIELDS) * 2 + 1, column=0, sticky="w", pady=(12, 0))

    def show(self, card):
        self.title.configure(text=card.name)
        for label, extract in FIELDS:
            self._values[label].configure(text=extract(card))
        self._show_image(card)
        # force the pending layout pass before resetting scroll, otherwise
        # this runs against the previous card's geometry and the reset lands
        # on the wrong fraction once Tk catches up
        self.update_idletasks()
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._canvas.yview_moveto(0)

    def clear(self):
        self.title.configure(text="No card selected")
        for label, _ in FIELDS:
            self._values[label].configure(text="")
        self._clear_image()

    # the Canvas is a plain tk widget, not ttk, so it does not pick up
    # ttk.Style changes on its own and needs its background set directly
    def apply_theme(self, colors):
        self._canvas.configure(background=colors["bg"])

    # -- card art ------------------------------------------------------

    def _show_image(self, card):
        self._request_token += 1
        token = self._request_token
        self._pending_token = None

        if not card.image_url:
            self._clear_image()
            return

        cached = self._image_cache.get(card.image_url)
        if cached is not None:
            self._set_image(cached)
            return

        self._clear_image()
        self._pending_token = token
        url = card.image_url

        def fetch():
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    data = response.read()
                self._image_events.put((token, url, data, None))
            except Exception as exc:  # network failure just leaves the art blank
                self._image_events.put((token, url, None, exc))

        threading.Thread(target=fetch, daemon=True).start()
        self.after(POLL_MS, self._drain_image_events)

    def _drain_image_events(self):
        try:
            while True:
                token, url, data, _error = self._image_events.get_nowait()
                if token == self._pending_token:
                    self._pending_token = None
                if token != self._request_token:
                    continue  # superseded by a later selection
                if data is not None:
                    photo = tk.PhotoImage(data=data)
                    if IMAGE_SUBSAMPLE > 1:
                        photo = photo.subsample(IMAGE_SUBSAMPLE)
                    self._image_cache[url] = photo
                    self._set_image(photo)
        except queue.Empty:
            pass
        if self._pending_token is not None:
            self.after(POLL_MS, self._drain_image_events)

    def _set_image(self, photo):
        self.image_label.configure(image=photo)
        self.image_label.image = photo  # keep a reference so Tk doesn't free it

    def _clear_image(self):
        self.image_label.configure(image="")
        self.image_label.image = None
