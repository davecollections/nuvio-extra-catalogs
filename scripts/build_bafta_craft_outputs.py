#!/usr/bin/env python3
"""Generate and validate BAFTA Television Craft movie and series catalogues."""

from bafta_outputs import CRAFT_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(CRAFT_CONFIG))
