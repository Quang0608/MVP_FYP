"""Client for the official IMF PortWatch ArcGIS REST layers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx


PORTS_QUERY_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
    "Daily_Ports_Data/FeatureServer/0/query"
)
CHECKPOINTS_QUERY_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
    "Daily_Chokepoints_Data/FeatureServer/0/query"
)
DISRUPTIONS_QUERY_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
    "portwatch_disruptions_database/FeatureServer/0/query"
)
MAX_RECORD_COUNT = 1000

PORT_FIELDS = (
    "date,year,month,day,portid,portname,country,ISO3,"
    "portcalls_container,portcalls_dry_bulk,portcalls_general_cargo,"
    "portcalls_roro,portcalls_tanker,portcalls_cargo,portcalls,"
    "import_container,import_dry_bulk,import_general_cargo,import_roro,"
    "import_tanker,import_cargo,import,export_container,export_dry_bulk,"
    "export_general_cargo,export_roro,export_tanker,export_cargo,export"
)
CHECKPOINT_FIELDS = (
    "date,year,month,day,portid,portname,n_container,n_dry_bulk,"
    "n_general_cargo,n_roro,n_tanker,n_cargo,n_total,capacity_container,"
    "capacity_dry_bulk,capacity_general_cargo,capacity_roro,capacity_tanker,"
    "capacity_cargo,capacity"
)
DISRUPTION_FIELDS = (
    "eventid,eventtype,eventname,htmlname,htmldescription,alertlevel,country,"
    "fromdate,year,todate,severitytext,lat,long,editdate,affectedports,"
    "n_affectedports,affectedpopulation,pageid"
)
DatasetType = Literal["ports", "checkpoints"]


@dataclass
class PortWatchResult:
    pages: list[dict[str, Any]]
    records: list[dict[str, Any]]
    request_details: dict[str, Any]


def _iso_timestamp(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_date_range(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")


def _where_clause(start_date: date, end_date: date, iso3: list[str] | None) -> str:
    clauses = [
        f"date >= DATE '{start_date.isoformat()}'",
        f"date <= DATE '{end_date.isoformat()}'",
    ]
    if iso3:
        normalized = [value.upper() for value in iso3]
        if any(len(value) != 3 or not value.isalpha() for value in normalized):
            raise ValueError("ISO3 filters must be three alphabetic characters")
        clauses.append("(" + " OR ".join(f"ISO3 = '{value}'" for value in normalized) + ")")
    return " AND ".join(clauses)


class PortWatchClient:
    """Query PortWatch and retain each ArcGIS response page unchanged."""

    def __init__(
        self,
        client: httpx.Client | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PortWatchClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch(
        self,
        dataset_type: DatasetType,
        start_date: date,
        end_date: date,
        iso3: list[str] | None = None,
    ) -> PortWatchResult:
        _validate_date_range(start_date, end_date)
        if dataset_type == "ports":
            endpoint = PORTS_QUERY_URL
            out_fields = PORT_FIELDS
        else:
            endpoint = CHECKPOINTS_QUERY_URL
            out_fields = CHECKPOINT_FIELDS

        where = _where_clause(start_date, end_date, iso3 if dataset_type == "ports" else None)
        pages: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            params = {
                "where": where,
                "outFields": out_fields,
                "returnGeometry": "false",
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": MAX_RECORD_COUNT,
            }
            response = self._client.get(endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(f"PortWatch API returned an error: {payload['error']}")
            features = payload.get("features")
            if not isinstance(features, list):
                raise RuntimeError("PortWatch API response did not contain a features list")
            pages.append(payload)
            records.extend(
                feature.get("attributes", {})
                for feature in features
                if isinstance(feature, dict)
            )
            if not features or (
                len(features) < MAX_RECORD_COUNT
                and not payload.get("exceededTransferLimit", False)
            ):
                break
            offset += len(features)

        request_details = {
            "method": "GET",
            "url": endpoint,
            "where": where,
            "outFields": out_fields,
            "returnGeometry": False,
            "format": "json",
            "page_size": MAX_RECORD_COUNT,
            "iso3": iso3 if dataset_type == "ports" else None,
            "page_count": len(pages),
        }
        return PortWatchResult(pages, records, request_details)

    def fetch_disruptions(self, where: str = "1=1") -> PortWatchResult:
        """Fetch the official PortWatch disruption layer without source filtering."""

        if not where.strip():
            raise ValueError("where must not be empty")
        pages: list[dict[str, Any]] = []
        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            params = {
                "where": where,
                "outFields": DISRUPTION_FIELDS,
                "returnGeometry": "false",
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": MAX_RECORD_COUNT,
            }
            response = self._client.get(DISRUPTIONS_QUERY_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(
                    f"PortWatch API returned an error: {payload['error']}"
                )
            features = payload.get("features")
            if not isinstance(features, list):
                raise RuntimeError(
                    "PortWatch disruption response did not contain a features list"
                )
            pages.append(payload)
            records.extend(
                feature.get("attributes", {})
                for feature in features
                if isinstance(feature, dict)
            )
            if not features or (
                len(features) < MAX_RECORD_COUNT
                and not payload.get("exceededTransferLimit", False)
            ):
                break
            offset += len(features)

        request_details = {
            "method": "GET",
            "url": DISRUPTIONS_QUERY_URL,
            "where": where,
            "outFields": DISRUPTION_FIELDS,
            "returnGeometry": False,
            "format": "json",
            "page_size": MAX_RECORD_COUNT,
            "page_count": len(pages),
        }
        return PortWatchResult(pages, records, request_details)


def save_raw_extraction(
    *,
    dataset_type: Literal["ports", "checkpoints"],
    start_date: date,
    end_date: date,
    result: PortWatchResult,
    raw_root: Path = Path("data/raw/portwatch"),
    retrieved_at: datetime | None = None,
) -> Path:
    """Save an immutable dated raw extraction and its metadata."""

    _validate_date_range(start_date, end_date)
    extraction_dir = raw_root / dataset_type / f"{start_date}_{end_date}"
    if extraction_dir.exists() and any(extraction_dir.iterdir()):
        raise FileExistsError(
            f"Raw extraction already exists and is immutable: {extraction_dir}"
        )
    extraction_dir.mkdir(parents=True, exist_ok=True)
    (extraction_dir / "response.json").write_text(
        json.dumps({"pages": result.pages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metadata = {
        "source": "IMF_PORTWATCH",
        "dataset_type": dataset_type,
        "retrieved_at": _iso_timestamp(retrieved_at),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "record_count": len(result.records),
        "request": result.request_details,
        "raw_response_format": "ordered_arcgis_pages",
    }
    (extraction_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return extraction_dir


def save_raw_disruption_snapshot(
    *,
    result: PortWatchResult,
    raw_root: Path = Path("data/raw/portwatch"),
    retrieved_at: datetime | None = None,
) -> Path:
    """Save an immutable disruption snapshot under its retrieval timestamp."""

    retrieved = retrieved_at or datetime.now(timezone.utc)
    timestamp = _iso_timestamp(retrieved)
    directory_name = timestamp.replace("-", "").replace(":", "").replace(".", "")
    directory = raw_root / "disruptions" / directory_name
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(
            f"Raw disruption snapshot already exists and is immutable: {directory}"
        )
    directory.mkdir(parents=True, exist_ok=True)
    response_payload: Any = (
        result.pages[0] if len(result.pages) == 1 else {"pages": result.pages}
    )
    (directory / "response.json").write_text(
        json.dumps(response_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metadata = {
        "source": "IMF_PORTWATCH",
        "dataset_type": "disruptions",
        "retrieved_at": timestamp,
        "record_count": len(result.records),
        "request": result.request_details,
        "raw_response_format": "arcgis_response"
        if len(result.pages) == 1
        else "ordered_arcgis_pages",
    }
    (directory / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return directory


def load_raw_records(extraction_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read the saved raw page bundle without changing source attributes."""

    response_path = extraction_dir / "response.json"
    metadata_path = extraction_dir / "metadata.json"
    bundle = json.loads(response_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    pages = bundle.get("pages", [])
    records: list[dict[str, Any]] = []
    for page in pages:
        records.extend(
            feature.get("attributes", {})
            for feature in page.get("features", [])
            if isinstance(feature, dict)
        )
    return records, metadata


def load_raw_disruption_records(
    snapshot_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read one raw disruption snapshot without changing source attributes."""

    response_path = snapshot_dir / "response.json"
    metadata_path = snapshot_dir / "metadata.json"
    payload = json.loads(response_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    pages = payload.get("pages") if isinstance(payload, dict) else None
    if pages is None:
        pages = [payload]
    records: list[dict[str, Any]] = []
    for page in pages:
        records.extend(
            feature.get("attributes", {})
            for feature in page.get("features", [])
            if isinstance(feature, dict)
        )
    return records, metadata
