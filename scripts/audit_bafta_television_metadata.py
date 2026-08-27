#!/usr/bin/env python3
"""Audit metadata compatibility for published BAFTA Television catalogues."""

from bafta_metadata import TELEVISION_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(TELEVISION_CONFIG))
