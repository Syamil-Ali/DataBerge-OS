import sys
sys.path.insert(0, "backend")
from app.services.opendosm import fetch_profile_only
try:
    result = fetch_profile_only("cpi_core")
    print(f"OK — {result['row_count']} rows, {result['column_count']} columns")
except Exception as e:
    print(f"FAILED: {e}")