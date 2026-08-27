#!/usr/bin/env python3
"""Build canonical BAFTA Film data from the reviewed first-party snapshot."""

from bafta_canonical import FILM_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(FILM_CONFIG))
