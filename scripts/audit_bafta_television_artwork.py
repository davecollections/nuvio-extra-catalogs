#!/usr/bin/env python3
"""Audit published BAFTA Television posters through the production artwork path."""

from bafta_artwork import TELEVISION_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(TELEVISION_CONFIG))
