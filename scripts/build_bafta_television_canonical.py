#!/usr/bin/env python3
"""Build canonical BAFTA Television data from the reviewed first-party snapshot."""

from bafta_canonical import TELEVISION_CONFIG, main


if __name__ == "__main__":
    raise SystemExit(main(TELEVISION_CONFIG))
