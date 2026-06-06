import json
from datetime import datetime, timezone
from adapters.lee_county import LeeCountyAdapter

adapter = LeeCountyAdapter()
fetched_at = datetime.now(timezone.utc)
raw = adapter.fetch_raw()

print(f"Type: {type(raw).__name__}, Length: {len(raw) if hasattr(raw, '__len__') else 'N/A'}")
print("\n--- First raw record ---")
print(json.dumps(raw[0], indent=2))

print("\n--- Normalized ---")
print(adapter.normalize(raw[0], fetched_at).model_dump_json(indent=2))

print("\n--- Last 3 normalized (sanity check timestamps & nulls) ---")
for r in raw[-3:]:
    n = adapter.normalize(r, fetched_at)
    print(f"  {n.occurred_at}  {n.nature}  {n.city}")