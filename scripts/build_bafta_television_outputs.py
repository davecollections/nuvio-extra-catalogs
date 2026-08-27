#!/usr/bin/env python3
"""Generate and validate BAFTA Television movie and series catalogues."""

from bafta_outputs import TELEVISION_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(TELEVISION_CONFIG))
