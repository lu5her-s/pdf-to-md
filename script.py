#!/usr/bin/env python3
"""
Root-level entry point for pdf_to_md.

Usage:
    python script.py input.pdf [options...]

This is a thin wrapper that imports ``main()`` from the ``pdf_to_md`` package.
"""

from pdf_to_md import main

if __name__ == "__main__":
    main()
