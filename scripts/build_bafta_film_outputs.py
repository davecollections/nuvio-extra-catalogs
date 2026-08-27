#!/usr/bin/env python3
"""Generate and validate BAFTA Film movie and series catalogues."""

from bafta_outputs import FILM_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(FILM_CONFIG))
