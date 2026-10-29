"""Application state shared by every callback: the loaded dataset and the edits store."""

import threading
from datetime import date

from ..data.dataset import load_dataset
from ..data.files import declared_hash
from ..edits.apply import apply_edits
from ..edits.store import FILE_NAME, EditStore


class AppState:
    """
    The dashboard runs locally for a single user, so the dataset lives in
    memory for the life of the server. `reload()` re-reads the data folder,
    for example when the day's capture arrives. Edits are read from the
    store on every request, so a saved correction is visible at once.
    """

    def __init__(self, settings, today=date.today):
        self.settings = settings
        self._today = today
        self._lock = threading.Lock()
        self.store = EditStore(settings.user_data_dir / FILE_NAME)
        self.dataset = None
        self.reload()

    def reload(self):
        dataset = load_dataset(self.settings.data_dir)
        with self._lock:
            self.dataset = dataset
        return dataset

    def today(self):
        return self._today()

    def edits(self):
        return self.store.snapshot()

    def declared_hash(self):
        path = self.settings.expected_hash_file
        return declared_hash(path) if path else None

    def operation(self, operation_id):
        """
        The operation with that ID as rebuilt, without edits, from the most
        recent capture that contains it (as in multi-day ranges), or None.
        """
        dataset = self.dataset
        for day in reversed(dataset.usable_dates):
            for op in dataset.captures[day].operations:
                if op.id == operation_id:
                    return op
        return None

    def classified(self, operation_id):
        """The same operation with its edits applied, or None."""
        op = self.operation(operation_id)
        return apply_edits([op], self.edits())[0] if op is not None else None
