#!/usr/bin/env python3
"""Audit BAFTA Television Craft titles through production metadata providers."""

from bafta_metadata import CRAFT_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(CRAFT_CONFIG))
