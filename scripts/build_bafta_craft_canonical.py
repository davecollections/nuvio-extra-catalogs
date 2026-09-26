#!/usr/bin/env python3
"""Build canonical BAFTA Television Craft data from reviewed source evidence."""

from bafta_canonical import CRAFT_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(CRAFT_CONFIG))
