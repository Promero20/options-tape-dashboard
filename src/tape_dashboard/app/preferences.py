"""
The user's interface preferences, in preferences.json in the user-data folder
(decision 0035). For now, the saved layout of the operations list.

The file is written atomically (a temporary file, then a replace). If it
cannot be read, factory settings are used, a warning says so, and the file is
not touched; saving over it first keeps a copy of it.
"""

import json
import os
import shutil
from pathlib import Path

FILE_NAME = "preferences.json"
OPERATIONS_COLUMNS = "operations_columns"


class Preferences:
    def __init__(self, path):
        self.path = Path(path)

    def _read(self):
        """(content, problem): the content is {} if the file is missing or cannot be read."""
        if not self.path.is_file():
            return {}, None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            return {}, f"{self.path.name} cannot be read: factory settings are used, and the file is left as it is."
        if not isinstance(data, dict):
            return {}, f"{self.path.name} is not a JSON object: factory settings are used, and the file is left " \
                       f"as it is."
        layout = data.get(OPERATIONS_COLUMNS)
        if layout is not None and not _is_layout(layout):
            return data, f"The saved layout of the operations list in {self.path.name} is not valid: factory " \
                         f"columns are used."
        return data, None

    def problem(self):
        return self._read()[1]

    def operations_columns(self):
        """The saved layout of the operations list, or None."""
        data, _ = self._read()
        layout = data.get(OPERATIONS_COLUMNS)
        return layout if _is_layout(layout) and layout else None

    def save_operations_columns(self, layout):
        data, problem = self._read()
        if problem and not data:            # unreadable: keep it before writing a new one
            shutil.copy2(self.path, self.path.with_name(self.path.name + ".unreadable"))
        self._write({**data, OPERATIONS_COLUMNS: layout})

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)


def _is_layout(value):
    return isinstance(value, list) and all(isinstance(e, dict) and isinstance(e.get("colId"), str) for e in value)
