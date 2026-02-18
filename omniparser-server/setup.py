"""Setup script: clones OmniParser repo and creates the import shim.

Run this once after creating the venv and installing requirements:
    python setup.py
    python download_models.py
    python server.py
"""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OMNIPARSER_DIR = os.path.join(SCRIPT_DIR, "OmniParser")


def main():
    # Step 1: Clone OmniParser if not present
    if os.path.isdir(OMNIPARSER_DIR):
        print(f"OmniParser already cloned at {OMNIPARSER_DIR}")
    else:
        print("Cloning Microsoft OmniParser V2...")
        subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/microsoft/OmniParser.git", OMNIPARSER_DIR],
            check=True,
        )
        print("Cloned.")

    # Step 2: Verify util/utils.py exists
    utils_path = os.path.join(OMNIPARSER_DIR, "util", "utils.py")
    if not os.path.exists(utils_path):
        print(f"ERROR: Expected {utils_path} not found. Clone may be corrupted.")
        sys.exit(1)

    print(f"\nOmniParser source ready at {OMNIPARSER_DIR}")
    print("Next steps:")
    print("  1. python download_models.py   # download YOLO + Florence-2 weights")
    print("  2. python server.py            # start the vision server")


if __name__ == "__main__":
    main()
