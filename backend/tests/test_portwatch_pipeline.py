import json
from datetime import date, datetime, timezone

import httpx
import pandas as pd
import pytest

from backend.data_pipeline.portwatch.build_state import (
    build_checkpoint_state,
    build_port_state,
)
from backend.data_pipeline.portwatch.build_features import build_port_features
from backend.data_pipeline.portwatch.build_current_disruptions import build_current_disruptions
from backend.data_pipeline.portwatch.build_port_master import build_port_master
from backend.data_pipeline.portwatch.client import (
    PortWatchClient,
    save_raw_disruption_snapshot,
    save_raw_extraction,
)
from backend.data_pipeline.portwatch.map_disruption_ports import map_disruption_ports
from backend.data_pipeline.portwatch.mapping import build_port_mapping, resolve_ports
from backend.data_pipeline.portwatch.normalize_disruptions import normalize_disruptions
from backend.data_pipeline.portwatch.normalize_checkpoints import normalize_checkpoints
from backend.data_pipeline.portwatch.normalize_ports import normalize_ports
from backend.data_pipeline.portwatch.impact import load_current_disruption_state


PORT_NUMERIC_FIELDS = [
    "portcalls_container",
    "portcalls_dry_bulk",
    "portcalls_general_cargo",
    "portcalls_roro",
    "portcalls_tanker",
    "portcalls_cargo",
    "portcalls",
    "import_container",
    "import_dry_bulk",
    "import_general_cargo",
    "import_roro",
    "import_tanker",
    "import_cargo",
    "import",
    "export_container",
    "export_dry_bulk",
    "export_general_cargo",
    "export_roro",
    "export_tanker",
    "export_cargo",
    "export",
]
CHECKPOINT_NUMERIC_FIELDS = [
    "n_container",
    "n_dry_bulk",
    "n_general_cargo",
    "n_roro",
    "n_tanker",
    "n_cargo",
    "n_total",
    "capacity_container",
    "capacity_dry_bulk",
    "capacity_general_cargo",
    "capacity_roro",
    "capacity_tanker",
    "capacity_cargo",
    "capacity",
]


DISRUPTION_FIELDS = [
    "eventid",
    "eventtype",
    "eventname",
    "htmlname",
    "htmldescription",
    "alertlevel",
    "country",
    "fromdate",
    "year",
    "todate",
    "severitytext",
    "lat",
    "long",
    "editdate",
    "affectedports",
    "n_affectedports",
    "affectedpopulation",
    "pageid",
]


def port_record(portid: str, portname: str, country: str, observation_date: str) -> dict:
    record = {
        "date": observation_date,
        "year": 2026,
        "month": 8,
        "day": 10,
        "portid": portid,
        "portname": portname,
        "country": country,
        "ISO3": "MYS",
    }
    record.update({field: 10 for field in PORT_NUMERIC_FIELDS})
    record["portcalls"] = 80
    record["import"] = 100000
    record["export"] = 120000
    return record


def checkpoint_record(observation_date: str) -> dict:
    record = {
        "date": observation_date,
        "year": 2026,
        "month": 8,
        "day": 10,
        "portid": "chokepoint1",
        "portname": "Suez Canal",
    }
    record.update({field: 10 for field in CHECKPOINT_NUMERIC_FIELDS})
    record["n_total"] = 90
    record["capacity"] = 9000000
    return record


def disruption_record(
    event_id: int,
    affected_ports: object,
    *,
    start: str = "2026-08-10T00:00:00Z",
    end: str | None = "2026-08-20T00:00:00Z",
    country: str = "Malaysia",
) -> dict:
    record = {field: None for field in DISRUPTION_FIELDS}
    record.update(
        {
            "eventid": event_id,
            "eventtype": "STRIKE",
            "eventname": f"Event {event_id}",
            "htmlname": f"<b>Event {event_id}</b>",
            "htmldescription": "Source disruption description",
            "alertlevel": "HIGH",
            "country": country,
            "fromdate": start,
            "year": 2026,
            "todate": end,
            "severitytext": "Severe",
            "lat": 3.0,
            "long": 101.38,
            "editdate": "2026-08-10T12:00:00Z",
            "affectedports": affected_ports,
            "n_affectedports": len(affected_ports) if isinstance(affected_ports, list) else 1,
            "affectedpopulation": "1000",
            "pageid": f"page-{event_id}",
        }
    )
    return record


def write_extraction(root, dataset: str, records: list[dict]) -> None:
    directory = root / dataset / "2026-08-10_2026-08-10"
    directory.mkdir(parents=True)
    (directory / "response.json").write_text(
        json.dumps({"pages": [{"features": [{"attributes": record} for record in records]}]}),
        encoding="utf-8",
    )
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "source": "IMF_PORTWATCH",
                "dataset_type": dataset,
                "retrieved_at": "2026-08-23T00:00:00Z",
                "start_date": "2026-08-10",
                "end_date": "2026-08-10",
                "record_count": len(records),
                "request": {"url": "fixture"},
            }
        ),
        encoding="utf-8",
    )


def write_disruption_snapshot(root, records: list[dict], timestamp: str = "20260823T000000Z") -> None:
    directory = root / "disruptions" / timestamp
    directory.mkdir(parents=True)
    (directory / "response.json").write_text(
        json.dumps({"features": [{"attributes": record} for record in records]}),
        encoding="utf-8",
    )
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "source": "IMF_PORTWATCH",
                "dataset_type": "disruptions",
                "retrieved_at": "2026-08-23T00:00:00Z",
                "record_count": len(records),
                "request": {"url": "fixture", "where": "1=1"},
            }
        ),
        encoding="utf-8",
    )


def test_client_paginates_and_preserves_page_payloads():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["resultOffset"])
        calls.append(offset)
        if offset == 0:
            features = [{"attributes": {"portid": str(index)}} for index in range(1000)]
            return httpx.Response(200, json={"features": features, "exceededTransferLimit": True})
        return httpx.Response(200, json={"features": [{"attributes": {"portid": "last"}}]})

    transport = httpx.MockTransport(handler)
    with PortWatchClient(httpx.Client(transport=transport)) as client:
        result = client.fetch("ports", date(2026, 8, 10), date(2026, 8, 16))

    assert calls == [0, 1000]
    assert len(result.pages) == 2
    assert len(result.records) == 1001
    assert result.request_details["page_size"] == 1000


def test_disruption_client_uses_official_layer_and_raw_snapshot_is_immutable(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        return httpx.Response(
            200,
            json={"features": [{"attributes": disruption_record(10, "Port Klang")}]},
        )

    transport = httpx.MockTransport(handler)
    with PortWatchClient(httpx.Client(transport=transport)) as client:
        result = client.fetch_disruptions("alertlevel = 'HIGH'")
        snapshot = save_raw_disruption_snapshot(
            result=result,
            raw_root=tmp_path,
            retrieved_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
    assert "portwatch_disruptions_database/FeatureServer/0/query" in str(calls[0])
    saved = json.loads((snapshot / "response.json").read_text(encoding="utf-8"))
    assert saved["features"][0]["attributes"]["eventid"] == 10
    with pytest.raises(FileExistsError):
        save_raw_disruption_snapshot(
            result=result,
            raw_root=tmp_path,
            retrieved_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )


def test_raw_extraction_is_immutable(tmp_path):
    result = type("Result", (), {
        "pages": [{"features": []}],
        "records": [],
        "request_details": {"url": "fixture"},
    })()
    save_raw_extraction(
        dataset_type="ports",
        start_date=date(2026, 8, 10),
        end_date=date(2026, 8, 10),
        result=result,
        raw_root=tmp_path,
    )
    with pytest.raises(FileExistsError):
        save_raw_extraction(
            dataset_type="ports",
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 10),
            result=result,
            raw_root=tmp_path,
        )


def test_port_and_checkpoint_normalization_reports_unresolved_and_preserves_nulls(tmp_path):
    raw_root = tmp_path / "raw"
    write_extraction(
        raw_root,
        "ports",
        [
            port_record("port1", "Port Klang", "Malaysia", "2026-08-10"),
            port_record("port-unknown", "Unknown Port", "Malaysia", "2026-08-10"),
        ],
    )
    write_extraction(raw_root, "checkpoints", [checkpoint_record("2026-08-10")])

    ports_output = tmp_path / "processed" / "port_monitoring.parquet"
    mapping_path = tmp_path / "mappings" / "wpi_portwatch_ports.csv"
    build_port_mapping(
        [port_record("port1", "Port Klang", "Malaysia", "2026-08-10"),
         port_record("port-unknown", "Unknown Port", "Malaysia", "2026-08-10")],
        wpi_path="data/processed/wpi/ports.parquet",
        mapping_path=mapping_path,
        review_path=tmp_path / "mappings" / "review.csv",
    )
    ports, port_report = normalize_ports(
        raw_root=raw_root,
        wpi_path="data/processed/wpi/ports.parquet",
        mapping_path=mapping_path,
        output_path=ports_output,
    )
    checkpoints_output = tmp_path / "processed" / "checkpoint_monitoring.parquet"
    checkpoints, checkpoint_report = normalize_checkpoints(
        raw_root=raw_root,
        mapping_path=tmp_path / "mappings" / "checkpoints.csv",
        output_path=checkpoints_output,
    )

    assert len(ports) == 1
    assert port_report["unresolved_ports"] == 1
    assert ports.iloc[0]["location_id"] == "LOC_WPI_49930"
    assert pd.isna(ports.iloc[0]["port_calls_container"]) is False
    assert len(checkpoints) == 1
    assert checkpoints.iloc[0]["checkpoint_id"] == "CHK_SUEZ_CANAL"
    assert checkpoint_report["matched_checkpoints"] == 1

    port_state = build_port_state(
        ports_output,
        tmp_path / "processed" / "current_port_state.parquet",
        activity_reference=100,
        pressure_reference=1_000_000,
    )
    checkpoint_state = build_checkpoint_state(
        checkpoints_output,
        tmp_path / "processed" / "current_checkpoint_state.parquet",
        activity_reference=100,
        pressure_reference=10_000_000,
    )
    assert port_state.iloc[0]["status"] == "HIGH_ACTIVITY"
    assert checkpoint_state.iloc[0]["status"] == "HIGH_ACTIVITY"
    features = pd.read_parquet(tmp_path / "processed" / "port_features.parquet")
    baselines = pd.read_parquet(tmp_path / "processed" / "port_baselines.parquet")
    assert {"port_calls_change_pct", "activity_anomaly_score"}.issubset(features.columns)
    assert baselines.iloc[0]["baseline_quality"] == "LIMITED_HISTORY"
    assert "operational_status" in port_state.columns


def test_port_features_calculate_recent_changes_and_anomalies(tmp_path):
    input_path = tmp_path / "port_monitoring.parquet"
    frame = pd.DataFrame(
        [
            {
                "location_id": "LOC_TEST",
                "observation_date": "2026-08-10",
                "port_calls_total": 10,
                "import_total": 100,
                "export_total": 200,
                "source_port_id": "test-port",
                "source": "PORTWATCH",
                "ingested_at": "2026-08-23T00:00:00Z",
            },
            {
                "location_id": "LOC_TEST",
                "observation_date": "2026-08-11",
                "port_calls_total": 20,
                "import_total": 200,
                "export_total": 100,
                "source_port_id": "test-port",
                "source": "PORTWATCH",
                "ingested_at": "2026-08-23T00:00:00Z",
            },
        ]
    )
    frame.to_parquet(input_path, index=False)

    features, baselines = build_port_features(
        input_path,
        tmp_path / "port_features.parquet",
        tmp_path / "port_baselines.parquet",
    )

    assert pd.isna(features.iloc[0]["port_calls_change_pct"])
    assert features.iloc[1]["port_calls_change_pct"] == 100.0
    assert baselines.iloc[0]["average_port_calls"] == 15.0
    assert baselines.iloc[0]["recent_change_percent"] == 100.0


def test_unified_port_master_retains_source_native_ports(tmp_path):
    source_records = [
        port_record("matched", "Port Klang", "Malaysia", "2026-08-10"),
        port_record("native", "Nakagusukuwan", "Japan", "2026-08-10"),
    ]
    source_mapping = tmp_path / "wpi_portwatch_mapping.csv"
    build_port_mapping(
        source_records,
        wpi_path="data/processed/wpi/ports.parquet",
        mapping_path=source_mapping,
        review_path=tmp_path / "review.csv",
    )
    master, report = build_port_master(
        wpi_path="data/processed/wpi/ports.parquet",
        source_mapping_path=source_mapping,
        output_dir=tmp_path / "processed" / "ports",
        master_mapping_path=tmp_path / "mappings" / "port_master_mapping.csv",
    )

    native = master[master.location_id == "PW_PORT_native"].iloc[0]
    matched = master[master.location_id == "LOC_WPI_49930"].iloc[0]
    assert native["canonical_source"] == "PORTWATCH"
    assert native["mapping_status"] == "SOURCE_NATIVE"
    assert pd.isna(native["wpi_number"])
    assert matched["mapping_status"] == "MATCHED_WPI"
    assert report["canonical_ports"] == 3803


def test_portwatch_normalization_keeps_source_native_observations(tmp_path):
    raw_root = tmp_path / "raw"
    records = [
        port_record("native", "Nakagusukuwan", "Japan", "2026-08-10"),
    ]
    write_extraction(raw_root, "ports", records)
    source_mapping = tmp_path / "wpi_portwatch_mapping.csv"
    build_port_mapping(
        records,
        wpi_path="data/processed/wpi/ports.parquet",
        mapping_path=source_mapping,
        review_path=tmp_path / "review.csv",
    )
    build_port_master(
        wpi_path="data/processed/wpi/ports.parquet",
        source_mapping_path=source_mapping,
        output_dir=tmp_path / "processed" / "ports",
        master_mapping_path=tmp_path / "mappings" / "port_master_mapping.csv",
    )
    normalized, report = normalize_ports(
        raw_root=raw_root,
        output_path=tmp_path / "processed" / "port_monitoring.parquet",
        port_master_mapping_path=tmp_path / "mappings" / "port_master_mapping.csv",
    )
    assert len(normalized) == 1
    assert normalized.iloc[0]["location_id"] == "PW_PORT_native"
    assert report["unresolved_ports"] == 0


def test_disruptions_normalize_map_and_build_current_state(tmp_path):
    raw_root = tmp_path / "raw"
    write_disruption_snapshot(
        raw_root,
        [
            disruption_record(10, "Port Klang"),
            disruption_record(
                11,
                ["Keppel - (East Singapore)"],
                start="2026-08-22T00:00:00Z",
                end=None,
                country="Singapore",
            ),
        ],
    )
    disruptions_path = tmp_path / "processed" / "disruptions.parquet"
    normalized, report = normalize_disruptions(
        raw_root=raw_root,
        output_path=disruptions_path,
    )
    assert len(normalized) == 2
    assert report["new_events"] == 2
    assert normalized.loc[normalized.event_id == "10", "affected_ports_raw"].item() == "Port Klang"

    affected_path = tmp_path / "processed" / "disruption_affected_ports.parquet"
    relations, mapping_report = map_disruption_ports(
        disruptions_path,
        affected_path,
        wpi_path="data/processed/wpi/ports.parquet",
        source_mapping_path=tmp_path / "missing-mapping.csv",
    )
    assert set(relations["location_id"]) == {"LOC_WPI_49930", "LOC_WPI_50000"}
    assert mapping_report["unresolved_affected_ports"] == 0

    current_path = tmp_path / "processed" / "current_disruptions.parquet"
    current, current_report = build_current_disruptions(
        disruptions_path,
        current_path,
        current_time="2026-08-23T00:00:00Z",
    )
    assert list(current.event_id) == ["11"]
    assert current_report["active_disruptions"] == 1
    impact_state = load_current_disruption_state(current_path, affected_path)
    assert impact_state[0]["affected_location_ids"] == ["LOC_WPI_50000"]


def test_disruption_event_updates_are_keyed_by_event_id(tmp_path):
    raw_root = tmp_path / "raw"
    write_disruption_snapshot(raw_root, [disruption_record(10, "Port Klang")])
    output = tmp_path / "processed" / "disruptions.parquet"
    first, _ = normalize_disruptions(raw_root=raw_root, output_path=output)
    assert first.loc[0, "alert_level"] == "HIGH"

    second_snapshot = raw_root / "disruptions" / "20260824T000000Z"
    second_snapshot.mkdir(parents=True)
    changed = disruption_record(10, "Port Klang")
    changed["alertlevel"] = "CRITICAL"
    (second_snapshot / "response.json").write_text(
        json.dumps({"features": [{"attributes": changed}]}), encoding="utf-8"
    )
    (second_snapshot / "metadata.json").write_text(
        json.dumps(
            {
                "source": "IMF_PORTWATCH",
                "dataset_type": "disruptions",
                "retrieved_at": "2026-08-24T00:00:00Z",
                "record_count": 1,
                "request": {"url": "fixture"},
            }
        ),
        encoding="utf-8",
    )
    second, report = normalize_disruptions(raw_root=raw_root, output_path=output)
    assert second.loc[0, "alert_level"] == "CRITICAL"
    assert report["updated_events"] == 1


def test_port_mapping_requires_wpi_name_and_country_match(tmp_path):
    records = [
        port_record("busan-mismatch", "Busan", "Korea", "2026-08-10"),
        port_record("busan-match", "Busan", "South Korea", "2026-08-10"),
    ]

    mapping_path = tmp_path / "mappings" / "wpi_portwatch_ports.csv"
    build_port_mapping(
        records,
        wpi_path="data/processed/wpi/ports.parquet",
        mapping_path=mapping_path,
        review_path=tmp_path / "mappings" / "review.csv",
    )
    resolved, mapping, unresolved = resolve_ports(
        records,
        mapping_path=mapping_path,
    )

    assert resolved["busan-mismatch"] == "LOC_WPI_60390"
    assert resolved["busan-match"] == "LOC_WPI_60390"
    assert (
        mapping.loc[
            mapping.source_port_id == "busan-mismatch", "match_method"
        ].item()
        == "AUTO_MATCHED_COUNTRY_ALIAS"
    )
    assert (
        mapping.loc[
            mapping.source_port_id == "busan-match", "match_method"
        ].item()
        == "AUTO_MATCHED_EXACT"
    )
    assert unresolved == []
