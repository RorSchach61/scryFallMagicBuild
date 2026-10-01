"""Light/dark color palettes and the ttk.Style wiring to apply them.

Windows' native ttk themes ('vista'/'xpnative') render each widget with the OS
theme engine and mostly ignore color overrides, so there would be no visible
difference between "light" and "dark" under them. 'clam' is a fully stylable,
platform-independent theme, so it is selected before any colors are applied.
"""
from tkinter import ttk

LIGHT = {
    "bg": "#f0f0f0",
    "fg": "#1a1a1a",
    "subtle_fg": "#595959",
    "field_bg": "#ffffff",
    "tree_bg": "#ffffff",
    "tree_fg": "#1a1a1a",
    "select_bg": "#0078d7",
    "select_fg": "#ffffff",
}

DARK = {
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "subtle_fg": "#9a9a9a",
    "field_bg": "#2d2d2d",
    "tree_bg": "#252526",
    "tree_fg": "#d4d4d4",
    "select_bg": "#094771",
    "select_fg": "#ffffff",
}


# ttk styles are global to the interpreter, not per-window, so this also
# re-themes any Toplevel (e.g. the sign-in gate, if reopened after sign out)
def apply_theme(root, dark):
    colors = DARK if dark else LIGHT
    style = ttk.Style(root)
    style.theme_use("clam")

    root.configure(background=colors["bg"])

    style.configure(".", background=colors["bg"], foreground=colors["fg"],
                     fieldbackground=colors["field_bg"])
    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
    style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg"])
    style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])

    style.configure("TButton", background=colors["field_bg"], foreground=colors["fg"])
    style.map("TButton", background=[("active", colors["select_bg"])],
              foreground=[("active", colors["select_fg"])])

    style.configure("TEntry", fieldbackground=colors["field_bg"], foreground=colors["fg"],
                     insertcolor=colors["fg"])

    style.configure("TNotebook", background=colors["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", background=colors["bg"], foreground=colors["fg"],
                     padding=(10, 4))
    style.map("TNotebook.Tab", background=[("selected", colors["field_bg"])])

    style.configure("TPanedwindow", background=colors["bg"])

    style.configure("TScrollbar", background=colors["bg"], troughcolor=colors["bg"],
                     arrowcolor=colors["fg"])

    style.configure("Treeview", background=colors["tree_bg"], foreground=colors["tree_fg"],
                     fieldbackground=colors["tree_bg"])
    style.map("Treeview", background=[("selected", colors["select_bg"])],
              foreground=[("selected", colors["select_fg"])])
    style.configure("Treeview.Heading", background=colors["bg"], foreground=colors["fg"])

    return colors
