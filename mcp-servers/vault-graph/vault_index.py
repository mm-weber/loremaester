"""Live index of a vault's notes (spec: specs/v0.2/surgical-search.md)."""

from pathlib import Path


class VaultIndex:
    def __init__(self, root) -> None:
        self.root = Path(root)
        self.notes: dict = {}

    def refresh(self) -> None:
        pass
