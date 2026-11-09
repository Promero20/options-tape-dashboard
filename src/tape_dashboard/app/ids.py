"""Component IDs shared across tabs. Tab-specific IDs live in each tab's layout module."""

RELOAD = "reload"
HEADER_INFO = "header-info"
NOTICES = "notices"
TABS = "tabs"

# Counters that other callbacks listen to: they change when the data folder
# is reloaded, when an edit is saved or when a position changes.
DATA_VERSION = "data-version"
EDITS_VERSION = "edits-version"
POSITIONS_VERSION = "positions-version"
