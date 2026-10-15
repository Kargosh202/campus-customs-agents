"""Reset the working database to the original shop data before a full run.

From HW 5/backend:
    ../.venv/bin/python reset_db.py

Copies data/campus_customs.db over data/campus_customs_new.db. The original is only read.
This also clears payment_requests and customer_drafts, which exist only in the working copy, and
records the reset time in data/last_reset.txt so the API doesn't reload runs from before the reset.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ORIGINAL = DATA_DIR / "campus_customs.db"
WORKING = DATA_DIR / "campus_customs_new.db"
RESET_MARKER = DATA_DIR / "last_reset.txt"

if __name__ == "__main__":
    shutil.copyfile(ORIGINAL, WORKING)
    RESET_MARKER.write_text(datetime.now(timezone.utc).isoformat(timespec="seconds") + "\n")
    print(f"Reset {WORKING.name} from {ORIGINAL.name}.")
