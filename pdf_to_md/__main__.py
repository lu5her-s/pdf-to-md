"""
Enable ``python -m pdf_to_md`` invocation.

This module is executed when the package is run as a script:
    python -m pdf_to_md input.pdf [options...]
"""

from pdf_to_md import main

if __name__ == "__main__":
    main()
