"""Normalize the World Port Index CSV into canonical port records."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from .validate_data import CanonicalPort


DEFAULT_INPUT = Path("data/raw/wpi/UpdatedPub150.csv")
DEFAULT_OUTPUT = Path("data/processed/wpi/ports.parquet")
OUTPUT_COLUMNS = [
    "location_id",
    "wpi_number",
    "name",
    "country",
    "unlocode",
    "latitude",
    "longitude",
    "location_type",
    "source",
]
REQUIRED_SOURCE_COLUMNS = {
    "OID_",
    "World Port Index Number",
    "Main Port Name",
    "UN/LOCODE",
    "Country Code",
    "Latitude",
    "Longitude",
}


def _clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_identifier(value: object) -> str:
    cleaned = _clean_text(value)
    if cleaned is None:
        raise ValueError("WPI identifiers cannot be blank")
    try:
        decimal_value = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric WPI identifier: {cleaned}") from exc
    if decimal_value == decimal_value.to_integral_value():
        return format(decimal_value.quantize(Decimal("1")), "f")
    return format(decimal_value.normalize(), "f")


def _clean_unlocode(value: object) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    return "".join(cleaned.split()).upper()


def normalize_wpi(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
) -> pd.DataFrame:
    """Normalize a WPI CSV and write the canonical ports Parquet file."""

    raw = pd.read_csv(
        input_path,
        dtype={"OID_": "string", "World Port Index Number": "string"},
        keep_default_na=False,
    )
    missing_columns = REQUIRED_SOURCE_COLUMNS - set(raw.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"WPI input is missing required columns: {missing}")
    if raw.empty:
        raise ValueError("WPI input contains no records")

    wpi_numbers = raw["World Port Index Number"].map(_clean_identifier)
    oids = raw["OID_"].map(_clean_identifier)
    names = raw["Main Port Name"].map(_clean_text)
    countries = raw["Country Code"].map(_clean_text)
    unlocodes = raw["UN/LOCODE"].map(_clean_unlocode)
    latitudes = pd.to_numeric(raw["Latitude"], errors="coerce")
    longitudes = pd.to_numeric(raw["Longitude"], errors="coerce")

    if names.isna().any() or countries.isna().any():
        raise ValueError("WPI names and countries must be nonblank")
    if latitudes.isna().any() or longitudes.isna().any():
        raise ValueError("WPI latitude and longitude must be numeric")
    if ((latitudes < -90) | (latitudes > 90)).any():
        raise ValueError("WPI latitude values must be between -90 and 90")
    if ((longitudes < -180) | (longitudes > 180)).any():
        raise ValueError("WPI longitude values must be between -180 and 180")

    duplicate_wpi_numbers = wpi_numbers.duplicated(keep=False)
    location_ids = []
    for wpi_number, oid, is_duplicate in zip(
        wpi_numbers, oids, duplicate_wpi_numbers, strict=True
    ):
        location_id = f"LOC_WPI_{wpi_number}"
        if is_duplicate:
            location_id = f"{location_id}_OID_{oid}"
        location_ids.append(location_id)

    normalized = pd.DataFrame(
        {
            "location_id": location_ids,
            "wpi_number": wpi_numbers,
            "name": names,
            "country": countries,
            "unlocode": unlocodes,
            "latitude": latitudes.astype(float),
            "longitude": longitudes.astype(float),
            "location_type": "PORT",
            "source": "WPI",
        },
        columns=OUTPUT_COLUMNS,
    )

    records = normalized.to_dict(orient="records")
    for record in records:
        if pd.isna(record["unlocode"]):
            record["unlocode"] = None
    validated_records = [
        CanonicalPort.model_validate(record).model_dump() for record in records
    ]
    validated = pd.DataFrame(validated_records, columns=OUTPUT_COLUMNS)
    if validated["location_id"].duplicated().any():
        raise ValueError("Normalized WPI location_id values are not unique")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    validated.to_parquet(output_path, index=False, engine="pyarrow")
    return validated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = normalize_wpi(args.input, args.output)
    print(f"Wrote {len(result)} canonical ports to {args.output}")


if __name__ == "__main__":
    main()
