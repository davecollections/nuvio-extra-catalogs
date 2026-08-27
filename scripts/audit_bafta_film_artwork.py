#!/usr/bin/env python3
"""Audit published BAFTA Film posters through the production artwork path."""

from bafta_artwork import FILM_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(FILM_CONFIG))
