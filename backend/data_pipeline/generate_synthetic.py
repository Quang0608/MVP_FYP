"""Synthetic enterprise-data generation interface."""

from pathlib import Path


def generate_synthetic_data(output_dir: Path) -> None:
    """Generate reproducible enterprise fixtures into ``output_dir``.

    The current deterministic fixture remains in ``backend/app/data.py``. A
    future generator should write canonical files and accept an explicit seed.
    """

    raise NotImplementedError(
        f"Synthetic canonical generation is not implemented for {output_dir}."
    )
