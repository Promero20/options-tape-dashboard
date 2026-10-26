"""Warnings shown in the banner above the tabs: nothing that goes wrong is silent."""

from dataclasses import dataclass

from ..data.issues import ERROR, INFO, WARNING
from ..edits.apply import orphans


@dataclass(frozen=True)
class Notice:
    level: str      # error / warning
    text: str


def collect(state):
    """Every notice worth showing, errors first."""
    notices = []
    settings, dataset = state.settings, state.dataset

    if not settings.data_dir.is_dir():
        notices.append(Notice(ERROR, f"The data folder does not exist: {settings.data_dir}"))

    script = dataset.script
    if settings.data_dir.is_dir() and not script.found:
        notices.append(Notice(WARNING, "The level-3 script is not in the data folder."))
    elif script.found and not script.matches:
        notices.append(Notice(
            WARNING,
            f"The level-3 script in the data folder (sha256 {script.deployed_sha256[:12]}…) differs from "
            f"pipeline/nivel3_agrupar.py ({script.canonical_sha256[:12]}…): deploy it again "
            f"(docs/level3-script.md)."))

    declared = state.declared_hash()
    if declared is not None and not declared.exists:
        notices.append(Notice(WARNING, f"The file with the pipeline's declared script hash was not found: "
                                       f"{declared.path}"))
    elif declared is not None and not declared.matches:
        notices.append(Notice(WARNING, f"The script hash declared in {declared.path.name} does not match "
                                       f"pipeline/nivel3_agrupar.py: update it after deploying."))

    for issue in dataset.issues:
        if issue.severity != INFO:
            where = f"{issue.file}: " if issue.file else ""
            notices.append(Notice(issue.severity, f"{where}{issue.message}"))

    for orphan in orphans(dataset, state.edits()):
        notices.append(Notice(WARNING, f"Orphan {orphan.kind} on {orphan.operation_id} ({orphan.detail}): "
                                       f"its operation no longer exists. It is kept, not deleted."))

    return sorted(notices, key=lambda n: n.level != ERROR)
