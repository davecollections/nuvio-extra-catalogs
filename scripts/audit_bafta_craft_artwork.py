#!/usr/bin/env python3
"""Audit BAFTA Television Craft posters through the production image routes."""

from bafta_artwork import CRAFT_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(CRAFT_CONFIG))
