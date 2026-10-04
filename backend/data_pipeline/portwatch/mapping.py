"""Build and consume persistent WPI-to-PortWatch entity mappings."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher, get_close_matches
from pathlib import Path
from typing import Any

import pandas as pd


PORT_MAPPING_COLUMNS = [
    "source_port_id",
    "source_port_name",
    "source_country",
    "source_iso3",
    "wpi_number",
    "wpi_name",
    "wpi_country",
    "canonical_location_id",
    "match_method",
    "similarity_score",
    "mapping_status",
    "review_sequence",
    "review_reason",
]
CHECKPOINT_MAPPING_COLUMNS = [
    "source_checkpoint_id",
    "source_checkpoint_name",
    "canonical_checkpoint_id",
    "match_method",
    "status",
]

AUTO_MAPPING_STATUSES = {"AUTO_MATCHED", "CONFIRMED", "MANUAL_CONFIRMED"}
FUZZY_AUTO_THRESHOLD = 0.86
FUZZY_REVIEW_THRESHOLD = 0.70
FUZZY_MARGIN = 0.04
GENERIC_NAME_TOKENS = {
    "bay",
    "canal",
    "de",
    "harbor",
    "harbour",
    "island",
    "islands",
    "la",
    "oil",
    "of",
    "port",
    "road",
    "terminal",
}

COUNTRY_ALIAS_GROUPS = [
    {"korea", "south korea", "republic of korea"},
    {"russia", "russian federation"},
    {"turkey", "turkiye"},
    {"cabo verde", "cape verde"},
    {"cote d ivoire", "ivory coast"},
    {"congo", "republic of congo"},
    {"democratic republic of the congo", "congo kinshasa"},
    {"democratic republic of the congo", "congo (kinshasa)"},
    {"myanmar", "burma"},
    {"vietnam", "viet nam"},
    {"netherlands", "the netherlands"},
    {"st kitts and nevis", "saint kitts and nevis"},
    {"st lucia", "saint lucia"},
    {
        "st vincent and the grenadines",
        "saint vincent and the grenadines windward islands",
    },
    {"united states virgin islands", "u s virgin islands"},
    {"hong kong sar", "hong kong"},
    {"macao sar", "macau"},
    {"taiwan province of china", "taiwan"},
    {
        "bonaire saint eustatius and saba",
        "caribbean netherlands",
    },
]


def normalize_name(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", normalized.lower()).strip()


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _existing_mapping(path: Path, columns: list[str]) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=columns)
    mapping = pd.read_csv(path, dtype="string", keep_default_na=False)
    missing = set(columns) - set(mapping.columns)
    if missing:
        raise ValueError(
            f"Mapping file is missing columns: {', '.join(sorted(missing))}"
        )
    return mapping[columns]


def _country_group_key(value: object) -> str:
    normalized = normalize_name(value)
    for group in COUNTRY_ALIAS_GROUPS:
        if normalized in group:
            return sorted(group)[0]
    return normalized


def _countries_compatible(source_country: object, wpi_country: object) -> bool:
    return _country_group_key(source_country) == _country_group_key(wpi_country)


def _meaningful_tokens(name_key: str) -> set[str]:
    return {
        token
        for token in name_key.split()
        if token and token not in GENERIC_NAME_TOKENS
    }


def _candidate_similarity(
    source_name_key: str,
    candidates: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, float | None, str]:
    """Return a deterministic candidate and its review classification."""

    by_name: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        by_name.setdefault(candidate["_name_key"], []).append(candidate)
    if not by_name or not source_name_key:
        return None, None, "NO_SIMILAR_NAME"

    close_names = get_close_matches(
        source_name_key,
        sorted(by_name),
        n=5,
        cutoff=FUZZY_REVIEW_THRESHOLD,
    )
    scored = sorted(
        (
            SequenceMatcher(None, source_name_key, candidate_name).ratio(),
            candidate_name,
        )
        for candidate_name in close_names
    )
    if not scored:
        return None, None, "NO_SIMILAR_NAME"

    score, candidate_name = scored[-1]
    second_score = scored[-2][0] if len(scored) > 1 else 0.0
    rows = by_name[candidate_name]
    shared_tokens = _meaningful_tokens(source_name_key).intersection(
        _meaningful_tokens(candidate_name)
    )
    if not shared_tokens:
        return None, score, "NO_MEANINGFUL_NAME_TOKEN"
    if len(rows) != 1 or score - second_score < FUZZY_MARGIN:
        return None, score, "AMBIGUOUS_SIMILAR_NAME"
    if score >= FUZZY_AUTO_THRESHOLD:
        return rows[0], score, "AUTO_MATCHED_FUZZY"
    return rows[0], score, "REVIEW_SIMILAR_NAME"


def _mapping_row(
    source_id: str,
    source_record: dict[str, Any],
    *,
    candidate: dict[str, Any] | None = None,
    method: str,
    score: float | None = None,
    status: str,
    reason: str = "",
) -> dict[str, str]:
    return {
        "source_port_id": source_id,
        "source_port_name": _text(source_record.get("portname")),
        "source_country": _text(source_record.get("country")),
        "source_iso3": _text(source_record.get("ISO3")),
        "wpi_number": _text(candidate.get("wpi_number")) if candidate else "",
        "wpi_name": _text(candidate.get("name")) if candidate else "",
        "wpi_country": _text(candidate.get("country")) if candidate else "",
        "canonical_location_id": (
            _text(candidate.get("location_id")) if candidate else ""
        ),
        "match_method": method,
        "similarity_score": f"{score:.6f}" if score is not None else "",
        "mapping_status": status,
        "review_sequence": "",
        "review_reason": reason,
    }


def build_port_mapping(
    source_records: list[dict[str, Any]],
    *,
    wpi_path: Path = Path("data/processed/wpi/ports.parquet"),
    mapping_path: Path = Path("data/mappings/wpi_portwatch_port_mapping.csv"),
    review_path: Path = Path("data/mappings/wpi_portwatch_review_queue.csv"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create the persistent mapping table and numbered review queue.

    This is the only function that proposes matches. Normalization uses the
    saved mapping table through :func:`resolve_ports` and does not call this
    matching logic.
    """

    wpi = pd.read_parquet(wpi_path).copy()
    required = {"location_id", "wpi_number", "name", "country"}
    if not required.issubset(wpi.columns):
        raise ValueError("WPI canonical port table lacks mapping columns")
    wpi["_name_key"] = wpi["name"].map(normalize_name)

    exact_candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    name_candidates: dict[str, list[dict[str, Any]]] = {}
    country_candidates: dict[str, list[dict[str, Any]]] = {}
    wpi_rows = wpi.to_dict(orient="records")
    for row in wpi_rows:
        if not row["_name_key"]:
            continue
        exact_candidates.setdefault(
            (row["_name_key"], normalize_name(row["country"])), []
        ).append(row)
        name_candidates.setdefault(row["_name_key"], []).append(row)
        country_candidates.setdefault(_country_group_key(row["country"]), []).append(row)

    existing = _existing_mapping(mapping_path, PORT_MAPPING_COLUMNS)
    confirmed = {
        row["source_port_id"]: row
        for row in existing.to_dict(orient="records")
        if row["source_port_id"]
        and row["canonical_location_id"]
        and row["mapping_status"] in {"CONFIRMED", "MANUAL_CONFIRMED"}
    }

    unique_sources: dict[str, dict[str, Any]] = {}
    for record in source_records:
        source_id = _text(record.get("portid"))
        if source_id:
            unique_sources[source_id] = record

    rows: list[dict[str, str]] = []
    for source_id, record in sorted(unique_sources.items()):
        if source_id in confirmed:
            previous = confirmed[source_id]
            rows.append(
                {
                    column: previous.get(column, "") for column in PORT_MAPPING_COLUMNS
                }
            )
            continue

        name_key = normalize_name(record.get("portname"))
        country_key = _country_group_key(record.get("country"))
        exact = exact_candidates.get(
            (name_key, normalize_name(record.get("country"))),
            [],
        )
        if len(exact) == 1:
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    candidate=exact[0],
                    method="AUTO_MATCHED_EXACT",
                    score=1.0,
                    status="AUTO_MATCHED",
                )
            )
            continue
        if len(exact) > 1:
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    method="AMBIGUOUS_NAME_COUNTRY",
                    status="REVIEW_REQUIRED",
                    reason="Multiple WPI ports share this normalized name and country.",
                )
            )
            continue

        same_name = name_candidates.get(name_key, [])
        alias_exact = [
            row
            for row in same_name
            if _country_group_key(row["country"]) == country_key
        ]
        if len(alias_exact) == 1:
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    candidate=alias_exact[0],
                    method="AUTO_MATCHED_COUNTRY_ALIAS",
                    score=1.0,
                    status="AUTO_MATCHED",
                    reason="Country labels were matched through an approved alias group.",
                )
            )
            continue
        if len(alias_exact) > 1:
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    method="AMBIGUOUS_NAME_COUNTRY",
                    status="REVIEW_REQUIRED",
                    reason="Multiple WPI ports share this name within the country alias group.",
                )
            )
            continue
        if len(same_name) == 1 and not _countries_compatible(
            record.get("country"), same_name[0].get("country")
        ):
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    candidate=same_name[0],
                    method="REVIEW_NAME_COUNTRY_ALIAS",
                    status="REVIEW_REQUIRED",
                    reason="Port name matches, but country labels are not in the approved alias groups.",
                )
            )
            continue
        if len(same_name) > 1:
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    method="AMBIGUOUS_NAME_COUNTRY",
                    status="REVIEW_REQUIRED",
                    reason="Port name matches multiple WPI records with different countries.",
                )
            )
            continue

        compatible_candidates = country_candidates.get(country_key, [])
        candidate, score, method = _candidate_similarity(name_key, compatible_candidates)
        if candidate is not None and method == "AUTO_MATCHED_FUZZY":
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    candidate=candidate,
                    method=method,
                    score=score,
                    status="AUTO_MATCHED",
                )
            )
        elif candidate is not None:
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    candidate=candidate,
                    method=method,
                    score=score,
                    status="REVIEW_REQUIRED",
                    reason="Candidate is similar but below the automatic confidence threshold.",
                )
            )
        else:
            rows.append(
                _mapping_row(
                    source_id,
                    record,
                    method=method,
                    status="UNMAPPED",
                    reason="No unique, country-compatible WPI candidate was found.",
                )
            )

    mapping = pd.DataFrame(rows, columns=PORT_MAPPING_COLUMNS)
    review_mask = ~mapping["mapping_status"].isin(AUTO_MAPPING_STATUSES)
    review = mapping.loc[review_mask].copy()
    if not review.empty:
        review_indices = review.index
        review["review_sequence"] = (
            pd.Series(range(1, len(review) + 1), index=review_indices).astype(str)
        )
        mapping.loc[review_indices, "review_sequence"] = review[
            "review_sequence"
        ].values
        review = review.reset_index(drop=True)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(mapping_path, index=False)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review.to_csv(review_path, index=False)
    return mapping, review


def resolve_ports(
    source_records: list[dict[str, Any]],
    *,
    mapping_path: Path = Path("data/mappings/wpi_portwatch_port_mapping.csv"),
) -> tuple[dict[str, str], pd.DataFrame, list[dict[str, str]]]:
    """Resolve source IDs using only the persistent mapping table."""

    mapping = _existing_mapping(mapping_path, PORT_MAPPING_COLUMNS)
    if mapping["source_port_id"].duplicated().any():
        raise ValueError("Persistent PortWatch mapping contains duplicate source IDs")
    mapping_by_id = {
        row["source_port_id"]: row for row in mapping.to_dict(orient="records")
    }
    unique_sources: dict[str, dict[str, Any]] = {}
    for record in source_records:
        source_id = _text(record.get("portid"))
        if source_id:
            unique_sources[source_id] = record

    resolved: dict[str, str] = {}
    unresolved: list[dict[str, str]] = []
    for source_id, record in sorted(unique_sources.items()):
        row = mapping_by_id.get(source_id)
        if row is None:
            unresolved.append(
                {
                    "source_port_id": source_id,
                    "source_port_name": _text(record.get("portname")),
                    "source_country": _text(record.get("country")),
                    "source_iso3": _text(record.get("ISO3")),
                    "mapping_status": "MAPPING_MISSING",
                    "review_reason": "No persistent mapping row exists for this source port ID.",
                }
            )
            continue
        if row["mapping_status"] in AUTO_MAPPING_STATUSES and row["canonical_location_id"]:
            resolved[source_id] = row["canonical_location_id"]
        else:
            unresolved.append(row)
    return resolved, mapping, unresolved


def _checkpoint_slug(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name.upper())
    return "CHK_" + "_".join(words) if words else ""


def resolve_checkpoints(
    source_records: list[dict[str, Any]],
    *,
    mapping_path: Path = Path("data/mappings/portwatch_checkpoint_mapping.csv"),
) -> tuple[dict[str, str], pd.DataFrame, list[dict[str, str]]]:
    """Resolve checkpoint IDs, honoring manual mappings before name slugs."""

    existing = _existing_mapping(mapping_path, CHECKPOINT_MAPPING_COLUMNS)
    manual = {
        row["source_checkpoint_id"]: row
        for row in existing.to_dict(orient="records")
        if row["source_checkpoint_id"] and row["canonical_checkpoint_id"]
    }
    unique_sources = {}
    for record in source_records:
        source_id = _text(record.get("portid"))
        if source_id:
            unique_sources[source_id] = record

    resolved: dict[str, str] = {}
    rows: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    for source_id, record in sorted(unique_sources.items()):
        name = _text(record.get("portname"))
        manual_row = manual.get(source_id)
        if manual_row:
            checkpoint_id = manual_row["canonical_checkpoint_id"]
            method = manual_row["match_method"] or "MANUAL"
            status = "MATCHED"
        else:
            checkpoint_id = _checkpoint_slug(name)
            method = "NAME_SLUG" if checkpoint_id else "MISSING_NAME"
            status = "MATCHED" if checkpoint_id else "UNRESOLVED"
        row = {
            "source_checkpoint_id": source_id,
            "source_checkpoint_name": name,
            "canonical_checkpoint_id": checkpoint_id,
            "match_method": method,
            "status": status,
        }
        rows.append(row)
        if status == "MATCHED":
            resolved[source_id] = checkpoint_id
        else:
            unresolved.append(row)

    mapping = pd.DataFrame(rows, columns=CHECKPOINT_MAPPING_COLUMNS)
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(mapping_path, index=False)
    return resolved, mapping, unresolved
