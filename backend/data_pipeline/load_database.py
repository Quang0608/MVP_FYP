"""Canonical database-loading interface."""

from pathlib import Path


def load_processed_data(processed_dir: Path) -> None:
    """Load validated canonical files into a future database adapter.

    The current repository uses SQLite and its existing structured repository;
    this function deliberately does not mutate that runtime path.
    """

    raise NotImplementedError(
        f"Processed-data loading is not implemented for {processed_dir}; approve a database adapter first."
    )
