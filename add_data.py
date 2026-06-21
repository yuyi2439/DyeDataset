"""Add new data
`data`: looks like:
```
{
    "segments": [
        {"dye": "system", "text": "xxx"},
        {"dye": "user", "text": "xxx"},
        ...
    ],
    "target": "xxx"
}
```
"""

import json5
import jsonl5

DATA_FILE = "v0.2.jsonl5"
NEW_DATA_FILE = ".newdata.json5"

with open(DATA_FILE) as f:
    datas = jsonl5.load(f)

_dataset = set(str(d) for d in datas)

with open(NEW_DATA_FILE) as f:
    new_data_raw = json5.load(f)

if isinstance(new_data_raw, dict):
    new_data_list = [new_data_raw]
elif isinstance(new_data_raw, list):
    new_data_list = new_data_raw
else:
    raise TypeError(f"Unsupported .newdata.json5 content type: {type(new_data_raw).__name__}")

unique_entries = []
duplicate_entries = []

for entry in new_data_list:
    entry_str = str(entry)
    if entry_str in _dataset:
        duplicate_entries.append(entry)
    else:
        unique_entries.append(entry)
        _dataset.add(entry_str)

if unique_entries:
    datas.extend(unique_entries)
    with open(DATA_FILE, "w") as f:
        jsonl5.dump(datas, f, ensure_ascii=False)

if duplicate_entries:
    raise ValueError(
        f"Found {len(duplicate_entries)} duplicate entries in {NEW_DATA_FILE}. "
        "Duplicate entries were skipped; unique entries were added."
    )

print("success")
