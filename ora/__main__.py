# ora/__main__.py
# Entry point: `python3 -m ora`
# Intentionally minimal — just initialise GTK and launch the app.

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .app import OraApp


def main() -> None:
    OraApp()
    Gtk.main()


if __name__ == "__main__":
    main()
