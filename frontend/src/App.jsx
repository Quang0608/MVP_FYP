import { useEffect, useMemo, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

const INACTIVE_SHIPMENT_STATUSES = new Set(["COMPLETED", "DELIVERED", "CANCELLED"]);
const REROUTE_QUEUE_RESULTS = new Set(["REROUTED", "NO_FEASIBLE_ROUTE"]);
const REROUTE_QUEUE_RESULT_OPTIONS = ["REROUTED", "NO_FEASIBLE_ROUTE"];

async function api(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : body.detail?.message;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return body;
}

function formatNumber(value, digits = 1) {
  return Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: digits,
  });
}

function formatMoney(value) {
  return `$${formatNumber(value, 0)}`;
}

function formatPercent(value) {
  return `${formatNumber(Number(value || 0) * 100, 0)}%`;
}

function titleCase(value) {
  return String(value || "")
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
}

function locationLabel(id, byId) {
  return byId[id]?.name || id;
}

function scenarioLabel(key) {
  return titleCase(key).replace("Singapore Closure", "Singapore Port Closure");
}

function routeKey(route) {
  return `${route.source_location_id}:${route.destination_location_id}`;
}

function pathEdges(path = []) {
  return new Set(path.slice(1).map((id, index) => `${path[index]}:${id}`));
}

function routeIntersectsDisruption(route, disruption) {
  if (!route || !disruption) return false;
  return (
    (route.location_ids || []).some((id) => (disruption.affected_location_ids || []).includes(id)) ||
    (route.route_ids || []).some((id) => (disruption.affected_route_ids || []).includes(id))
  );
}

function sameRoute(first, second) {
  return Boolean(first && second && JSON.stringify(first.location_ids || []) === JSON.stringify(second.location_ids || []));
}

function routeUtilization(route) {
  return route.capacity ? route.current_load / route.capacity : 0;
}

function combineDisruptions(disruptions) {
  if (!disruptions.length) return null;
  if (disruptions.length === 1) return { ...disruptions[0] };
  const severityRank = { LOW: 0, MEDIUM: 1, HIGH: 2 };
  const severity = disruptions.reduce((current, item) => severityRank[item.severity] > severityRank[current] ? item.severity : current, "LOW");
  return {
    disruption_type: "MULTIPLE_PORT",
    affected_location_ids: [...new Set(disruptions.flatMap((item) => item.affected_location_ids || []))],
    affected_route_ids: [...new Set(disruptions.flatMap((item) => item.affected_route_ids || []))],
    duration_hours: Math.max(...disruptions.map((item) => Number(item.duration_hours || 0))),
    severity,
    description: disruptions.map((item) => item.description || titleCase(item.disruption_type)).join("; "),
  };
}

function StatusPill({ children, tone = "neutral" }) {
  return <span className={`status-pill ${tone}`}>{children}</span>;
}

function Panel({ className = "", children, id }) {
  return (
    <section className={`panel ${className}`} id={id}>
      {children}
    </section>
  );
}

function PanelHeader({ eyebrow, title, action, children }) {
  return (
    <div className="panel-header">
      <div>
        {eyebrow && <p className="panel-eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
      </div>
      {action || children}
    </div>
  );
}

function FitNetwork({ locations }) {
  const map = useMap();

  useEffect(() => {
    if (!locations.length) return;
    map.fitBounds(
      locations.map((location) => [location.latitude, location.longitude]),
      { padding: [26, 26], maxZoom: 5 },
    );
  }, [locations, map]);

  return null;
}

function NetworkMap({ locations, routes, plan, disruption, layers }) {
  const byId = Object.fromEntries(locations.map((item) => [item.id, item]));
  const originalRouteUnaffected = Boolean(plan?.original_route && sameRoute(plan.original_route, plan.selected_route) && !routeIntersectsDisruption(plan.original_route, disruption));
  const selectedEdges = originalRouteUnaffected ? new Set() : pathEdges(plan?.selected_route?.location_ids);
  const originalEdges = pathEdges(plan?.original_route?.location_ids);
  const focusedPath = originalRouteUnaffected ? plan.original_route.location_ids : plan?.selected_route?.location_ids || plan?.original_route?.location_ids || null;
  const focusedIds = focusedPath ? new Set(focusedPath) : null;
  const visibleLocations = focusedIds ? locations.filter((location) => focusedIds.has(location.id)) : locations;
  const visibleEdges = focusedPath ? pathEdges(focusedPath) : null;
  const visibleRoutes = visibleEdges ? routes.filter((route) => visibleEdges.has(routeKey(route))) : routes;
  const showRouteEdges = Boolean(focusedPath || disruption);
  const disruptedLocations = new Set(disruption?.affected_location_ids || []);

  if (!locations.length) return <div className="network-map empty">Loading network...</div>;

  return (
    <div className="network-map-wrap">
      <MapContainer className="network-map" center={[12, 112]} zoom={3} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitNetwork locations={visibleLocations} />
        {layers.routes && showRouteEdges && visibleRoutes.map((route) => {
          const start = byId[route.source_location_id];
          const end = byId[route.destination_location_id];
          if (!start || !end) return null;
          const edge = routeKey(route);
          const blocked =
            route.status === "BLOCKED" ||
            disruptedLocations.has(route.source_location_id) ||
            disruptedLocations.has(route.destination_location_id);
          const utilization = routeUtilization(route);
          const selected = selectedEdges.has(edge);
          const original = originalEdges.has(edge);
          let color = "#52728f";
          if (blocked) color = "#f05b65";
          else if (selected) color = "#35d58a";
          else if (original) color = "#45a8ff";
          else if (layers.capacity && utilization >= 0.85) color = "#ff9d42";
          else if (layers.capacity && utilization >= 0.6) color = "#e5c14d";
          return (
            <Polyline
              key={route.id}
              positions={[[start.latitude, start.longitude], [end.latitude, end.longitude]]}
              pathOptions={{
                color,
                weight: selected ? 5 : blocked ? 3 : 2,
                opacity: blocked ? 0.9 : 0.75,
                dashArray: blocked || (layers.capacity && utilization >= 0.85) ? "7 5" : undefined,
              }}
            >
              <Tooltip sticky>
                {start.name} → {end.name} · {route.mode} · {formatPercent(utilization)} utilized
              </Tooltip>
            </Polyline>
          );
        })}
        {layers.locations && visibleLocations.map((location) => {
          const disrupted = disruptedLocations.has(location.id);
          const colors = {
            FACTORY: "#48a4ff",
            PORT: "#56d4d1",
            WAREHOUSE: "#35d58a",
            CUSTOMER: "#ae78ff",
          };
          const color = disrupted ? "#f05b65" : colors[location.type] || "#8ca3b9";
          return (
            <CircleMarker
              key={location.id}
              center={[location.latitude, location.longitude]}
              radius={disrupted ? 10 : 7}
              pathOptions={{ color, fillColor: color, fillOpacity: 0.96, weight: 2 }}
            >
              <Tooltip direction="top" offset={[0, -8]}>
                <strong>{location.name}</strong><br />
                {location.type} · {location.country}
                {location.source && <>
                  <br /><b>Source:</b> {location.source}
                  {location.latest_observation_date && <><br /><b>Latest observation:</b> {location.latest_observation_date}</>}
                  {location.activity_score != null && <><br /><b>Activity:</b> {formatPercent(location.activity_score)}</>}
                  {location.operational_status && <><br /><b>Status:</b> {titleCase(location.operational_status)}</>}
                </>}
                {disrupted && <><br /><b>DISRUPTED</b></>}
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
      <div className="map-status">OpenStreetMap · drag to pan · scroll to zoom</div>
      <div className="map-legend">
        <span><i className="legend-dot factory" />Factory</span>
        <span><i className="legend-dot port" />Port</span>
        <span><i className="legend-dot warehouse" />Warehouse</span>
        <span><i className="legend-dot customer" />Customer</span>
        {showRouteEdges && <><span><i className="legend-line active" />Active route</span>
        <span><i className="legend-line rerouted" />Rerouted</span>
        <span><i className="legend-line disrupted" />Disrupted</span></>}
      </div>
    </div>
  );
}

function Sidebar({ activeView, onNavigate }) {
  const groups = [
    { label: "Overview", items: [["overview", "⌂", "Command Center"]] },
    {
      label: "Monitor",
      items: [["network", "◈", "Supply Chain Map"], ["shipments", "▣", "Shipments"], ["locations", "⌖", "Locations"], ["disruptions", "♢", "Alerts & Events"]],
    },
    {
      label: "Analyze",
      items: [["disruptions", "◌", "Disruption Simulator"], ["shipments", "⌁", "Impact Analysis"], ["comparison", "◫", "Scenario Comparison"]],
    },
    {
      label: "Decide",
      items: [["recommendation", "▤", "Rerouting Recommendations"], ["comparison", "⌘", "Route Comparison"], ["action", "◉", "Action Center"]],
    },
    {
      label: "Evaluate",
      items: [["history", "▤", "Reports"]],
    },
    {
      label: "Admin",
      items: [["data", "▥", "Data Management"], ["settings", "⚙", "System Settings"]],
    },
  ];

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">◉</div>
        <div><strong>SC-Reroute</strong><small>AI Powered Command Center</small></div>
      </div>
      <nav>
        {groups.map((group) => (
          <div className="nav-group" key={group.label}>
            <p>{group.label}</p>
            {group.items.map(([view, icon, label]) => (
              <button
                className={activeView === view ? "nav-item active" : "nav-item"}
                key={`${view}-${label}`}
                onClick={() => onNavigate(view)}
              >
                <span className="nav-icon">{icon}</span>{label}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <button className="collapse-button" onClick={() => onNavigate("overview")}>‹ <span>Collapse</span></button>
    </aside>
  );
}

function KpiCard({ icon, label, value, delta, tone = "blue", note }) {
  return (
    <div className={`kpi-card ${tone}`}>
      <div className="kpi-icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        {delta && <small className={delta.startsWith("↑") ? "positive" : "muted-text"}>{delta} {note || "vs. original plan"}</small>}
      </div>
    </div>
  );
}

function AssistantPanel({ plan, byId, disruption, messages, question, setQuestion, onAsk, chatWorking }) {
  const explanation = plan?.explanation;
  const original = plan?.original_route;
  const originalIsDisrupted = routeIntersectsDisruption(original, disruption);
  const originalRouteUnaffected = Boolean(original && sameRoute(original, plan?.selected_route) && !originalIsDisrupted);
  const disruptionReason = disruption ? `${titleCase(disruption.disruption_type)} · ${disruption.affected_location_ids?.map((id) => locationLabel(id, byId)).join(", ") || disruption.affected_route_ids?.join(", ") || "selected network legs"}` : "";
  return (
    <Panel className="assistant-panel">
      <PanelHeader
        title="AI Supply Chain Assistant"
        action={<span className="online"><i /> Grounded {explanation?.source === "offline_deterministic" ? "offline" : "assistant"}</span>}
      />
      {messages.length > 0 && <div className="assistant-chat-log">{messages.map((message, index) => <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}><strong>{message.role === "user" ? "You" : "Assistant"}</strong><p>{message.text}</p>{message.source && <small>{message.source === "offline_deterministic" ? "Deterministic dashboard context" : "Provider response grounded in dashboard context"}</small>}</div>)}</div>}
      <form className="assistant-input-form" onSubmit={onAsk}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about this dashboard..." maxLength={500} disabled={chatWorking} /><button type="submit" disabled={chatWorking || !question.trim()}>{chatWorking ? "…" : "➤"}</button></form>
      <div className="recommendation-box">
        <div className="recommendation-heading"><strong>Current Recommendation</strong><StatusPill tone="success">Recommended</StatusPill></div>
        {!plan && <p className="muted-text">Plan a route to see whether the current applied disruption affects it.</p>}
        {plan && originalIsDisrupted && <div className="disruption-alert"><strong>Original route disrupted</strong><span>{disruptionReason}</span><small>{plan.reason || "The route intersects the applied disruption."}</small></div>}
        {originalRouteUnaffected ? (
          <div className="route-unaffected"><strong>Route not affected</strong><RouteSnapshot label="Original route" route={original} byId={byId} tone="before" /></div>
        ) : plan?.selected_route ? (
          <>
            <p>{originalIsDisrupted ? "Best available alternative, based on the before-and-after comparison:" : "Current backend-selected route, compared with the baseline:"}</p>
            <div className="route-snapshot-grid recommendation-snapshots"><RouteSnapshot label="Before · original route" route={original} byId={byId} tone="before" /><div className="route-transition">→</div><RouteSnapshot label="After · best available alternative" route={plan.selected_route} byId={byId} tone="after" /></div>
            <p className="recommendation-copy">The deterministic planner compared {plan.candidate_routes?.length || 0} capacity-feasible alternative route(s) and selected the highest-ranked result. The selected route changes the baseline by {formatNumber((original?.duration_hours || plan.selected_route.duration_hours) - plan.selected_route.duration_hours, 1)} hours and {formatMoney(plan.selected_route.cost - (original?.cost || plan.selected_route.cost))}.</p>
            <ul className="benefits"><li>Avoids blocked or disrupted legs</li><li>Preserves available route capacity</li><li>Selection remains backend-owned</li></ul>
          </>
        ) : plan && <div className="no-route-alert"><strong>No other way found</strong><p>{plan.reason || "There is no remaining route for this origin and destination under the applied disruption."}</p></div>}
      </div>
    </Panel>
  );
}

function DisruptionPanel({ scenarios, selectedKeys, onSelect, onRun, customScenario, customOpen, setCustomOpen, custom, setCustom, locations, routes, byId, onCustomSubmit, working }) {
  return (
    <Panel id="disruptions">
      <PanelHeader title={`Disruptions (${selectedKeys.length})`} action={<button className="text-button" onClick={() => setCustomOpen(!customOpen)}>{customOpen ? "Close" : "+ Custom"}</button>} />
      <p className="disruption-help">Select one or more scenarios. Map, metrics, and shipments update only after you run the selection.</p>
      <div className="disruption-list">
        {Object.entries(scenarios).map(([key, value]) => (
          <button className={`disruption-row ${selectedKeys.includes(key) ? "selected" : ""}`} key={key} onClick={() => onSelect(key)}>
            <span className={`severity-dot ${value.severity?.toLowerCase()}`} />
            <span className="disruption-copy"><strong>{scenarioLabel(key)}</strong><small>{value.affected_location_ids?.length ? value.affected_location_ids.map((id) => locationLabel(id, byId)).join(", ") : value.affected_route_ids?.join(", ")}</small><small>Duration: {value.duration_hours} hours</small></span>
            <StatusPill tone={selectedKeys.includes(key) ? "success" : value.severity?.toLowerCase() === "high" ? "danger" : "warning"}>{selectedKeys.includes(key) ? "Selected" : value.severity || "Medium"}</StatusPill>
          </button>
        ))}
        {customScenario && <button className={`disruption-row ${selectedKeys.includes("custom") ? "selected" : ""}`} onClick={() => onSelect("custom")}><span className="severity-dot high" /><span className="disruption-copy"><strong>Custom disruption</strong><small>{customScenario.description || "Operator-defined scenario"}</small><small>Duration: {customScenario.duration_hours} hours</small></span><StatusPill tone={selectedKeys.includes("custom") ? "success" : "warning"}>{selectedKeys.includes("custom") ? "Selected" : "Ready"}</StatusPill></button>}
      </div>
      {customOpen && (
        <form className="custom-form" onSubmit={onCustomSubmit}>
          <div className="form-row"><label>Type<select value={custom?.disruption_type || "PORT_CLOSURE"} onChange={(event) => setCustom((current) => ({ ...current, disruption_type: event.target.value }))}><option>PORT_CLOSURE</option><option>FACTORY_SHUTDOWN</option><option>ROUTE_BLOCKED</option><option>CONGESTION</option><option>MULTIPLE_PORT</option></select></label><label>Severity<select value={custom?.severity || "HIGH"} onChange={(event) => setCustom((current) => ({ ...current, severity: event.target.value }))}><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></label></div>
          <div className="form-row"><label>Duration (hours)<input type="number" min="1" max="720" value={custom?.duration_hours || 72} onChange={(event) => setCustom((current) => ({ ...current, duration_hours: Number(event.target.value) }))} /></label><label>Description<input value={custom?.description || ""} onChange={(event) => setCustom((current) => ({ ...current, description: event.target.value }))} placeholder="Optional operator note" /></label></div>
          <label>Locations<select multiple value={custom?.affected_location_ids || []} onChange={(event) => setCustom((current) => ({ ...current, affected_location_ids: [...event.target.selectedOptions].map((option) => option.value) }))}>{locations.map((location) => <option value={location.id} key={location.id}>{location.name}</option>)}</select></label>
          <label>Routes<select multiple value={custom?.affected_route_ids || []} onChange={(event) => setCustom((current) => ({ ...current, affected_route_ids: [...event.target.selectedOptions].map((option) => option.value) }))}>{routes.map((route) => <option value={route.id} key={route.id}>{route.id}: {route.source_location_id} → {route.destination_location_id}</option>)}</select></label>
          <div className="form-actions"><small>Choose at least one location or route.</small><button className="primary" disabled={working}>Add to selection</button></div>
        </form>
      )}
      <button className="primary full" onClick={onRun} disabled={working || !selectedKeys.length}>{working ? "Running simulation..." : "Run selected disruption"}</button>
    </Panel>
  );
}

function RouteComparison({ plan, byId }) {
  const routes = plan?.candidate_routes || [];
  const originalRouteUnaffected = Boolean(plan?.original_route && sameRoute(plan.original_route, plan.selected_route) && !routeIntersectsDisruption(plan.original_route, plan.disruption));
  if (originalRouteUnaffected || (plan?.status === "ROUTE_FOUND" && routes.length <= 1)) return null;
  return (
    <Panel id="comparison" className="route-panel">
      <PanelHeader title="Route Comparison" action={<button className="text-button">View full comparison</button>} />
      {!routes.length ? plan ? <div className="no-route-alert"><strong>No other ways available</strong><p>{plan.reason || "The original route is disrupted and no capacity-feasible alternative was found."}</p></div> : <p className="muted-text">Plan a route to compare backend-ranked alternatives.</p> : <div className="table-scroll"><table><thead><tr><th>Route</th><th>Total time</th><th>Cost</th><th>Delay saved</th><th>Risk score</th><th>Capacity</th></tr></thead><tbody>{routes.map((route, index) => <tr key={`${route.route_ids.join("-")}-${index}`} className={index === 0 ? "recommended-row" : ""}><td><strong>{index === 0 ? "Alternative 1" : `Alternative ${index + 1}`}</strong><small>{route.location_ids.map((id) => locationLabel(id, byId)).join(" → ")}</small>{index === 0 && <StatusPill tone="success">Recommended</StatusPill>}</td><td>{formatNumber(route.duration_hours)} h</td><td>{formatMoney(route.cost)}</td><td>{plan.original_route ? `${formatNumber(plan.original_route.duration_hours - route.duration_hours)} h` : "—"}</td><td>{formatNumber(route.risk_score * 100, 0)}%</td><td><span className="capacity-value">{route.capacity_feasible ? "Feasible" : "Over capacity"}</span><small>{formatPercent(route.capacity_penalty)} pressure</small></td></tr>)}</tbody></table></div>}
    </Panel>
  );
}

function RouteSnapshot({ label, route, byId, tone }) {
  return (
    <div className={`route-snapshot ${tone}`}>
      <div className="route-snapshot-heading"><strong>{label}</strong>{route ? <StatusPill tone={route.capacity_feasible ? "success" : "danger"}>{route.capacity_feasible ? "Capacity feasible" : "Over capacity"}</StatusPill> : <StatusPill tone="warning">Unavailable</StatusPill>}</div>
      {route ? (
        <>
          <strong className="route-snapshot-path">{route.location_ids.map((id) => locationLabel(id, byId)).join(" → ")}</strong>
          <div className="route-snapshot-stats"><span>Duration <b>{formatNumber(route.duration_hours)} h</b></span><span>Cost <b>{formatMoney(route.cost)}</b></span><span>Risk <b>{formatPercent(route.risk_score)}</b></span><span>Capacity pressure <b>{formatPercent(route.capacity_penalty)}</b></span></div>
        </>
      ) : <p className="muted-text">No feasible after-route was returned for this shipment.</p>}
    </div>
  );
}

function ShipmentAnalysis({ shipment, recommendation, analysis, byId }) {
  if (!analysis) return null;
  const sourceLabel = analysis.source === "offline_deterministic" ? "Deterministic offline summary" : "OpenAI summary";
  const candidates = recommendation.candidate_routes || [];
  return (
    <div className="shipment-analysis">
      <div className="analysis-heading"><div><p className="panel-eyebrow">Shipment impact analysis</p><strong>{shipment.id} before-and-after route review</strong></div><StatusPill tone="info">{sourceLabel}</StatusPill></div>
      <div className="analysis-summary"><strong>{analysis.summary}</strong><p>{analysis.reasoning_summary}</p></div>
      <div className="route-snapshot-grid"><RouteSnapshot label="Before · original route" route={recommendation.original_route} byId={byId} tone="before" /><div className="route-transition">→</div><RouteSnapshot label="After · selected reroute" route={recommendation.selected_route} byId={byId} tone="after" /></div>
      {candidates.length > 0 && <div className="alternative-route-list"><div className="alternative-route-heading"><strong>Available reroute options ({candidates.length})</strong><span>All candidates are generated and ranked by the deterministic backend.</span></div>{candidates.map((route, index) => { const selected = sameRoute(route, recommendation.selected_route); const durationDelta = route.duration_hours - (recommendation.original_route?.duration_hours || route.duration_hours); const costDelta = route.cost - (recommendation.original_route?.cost || route.cost); return <div className={`alternative-route ${selected ? "selected" : ""}`} key={`${route.route_ids.join("-")}-${index}`}><div className="alternative-route-title"><strong>{selected ? "Selected route" : `Alternative ${index + 1}`}</strong><StatusPill tone={selected ? "success" : "info"}>{selected ? "Recommended" : "Candidate"}</StatusPill></div><p>{route.location_ids.map((id) => locationLabel(id, byId)).join(" → ")}</p><div className="alternative-route-stats"><span>Duration <b>{formatNumber(route.duration_hours)} h ({durationDelta >= 0 ? "+" : ""}{formatNumber(durationDelta)} h)</b></span><span>Cost <b>{formatMoney(route.cost)} ({costDelta >= 0 ? "+" : ""}{formatMoney(costDelta)})</b></span><span>Risk <b>{formatPercent(route.risk_score)}</b></span><span>Capacity <b>{route.capacity_feasible ? "Feasible" : "Over capacity"}</b></span></div></div>; })}</div>}
      <div className="analysis-deltas"><span>Shipment status <b>{titleCase(shipment.status)}</b></span><span>Reroute result <b>{titleCase(recommendation.status)}</b></span><span>Delay saved <b>{formatNumber(recommendation.delay_saved_hours)} h</b></span><span>Additional cost <b>{formatMoney(recommendation.additional_cost)}</b></span></div>
    </div>
  );
}

function InteractiveRouteAnalysis({ plan, byId, disruption }) {
  if (!plan) return null;
  const original = plan.original_route;
  const selected = plan.selected_route;
  const candidates = plan.candidate_routes || [];
  const affectedLocationIds = new Set(disruption?.affected_location_ids || []);
  const affectedRouteIds = new Set(disruption?.affected_route_ids || []);
  const originalIsDisrupted = Boolean(original && ((original.location_ids || []).some((id) => affectedLocationIds.has(id)) || (original.route_ids || []).some((id) => affectedRouteIds.has(id))));
  const disruptionReason = disruption ? `${titleCase(disruption.disruption_type)} · ${disruption.affected_location_ids?.map((id) => locationLabel(id, byId)).join(", ") || disruption.affected_route_ids?.join(", ") || "selected network legs"}` : "";
  return (
    <Panel id="route-analysis" className="route-analysis-panel">
      <PanelHeader eyebrow="Interactive route analysis" title="Before-and-after route review" action={<StatusPill tone={plan.status === "ROUTE_FOUND" ? "success" : "warning"}>{titleCase(plan.status)}</StatusPill>} />
      {originalIsDisrupted && <div className="disruption-alert"><strong>Original route disrupted</strong><span>{disruptionReason}</span><small>{plan.reason || "The original route intersects the applied disruption."}</small></div>}
      <div className="analysis-summary"><strong>{plan.explanation?.summary || (selected ? "The deterministic planner selected the highest-ranked capacity-feasible route." : "No feasible route was returned.")}</strong><p>{plan.explanation?.reasoning_summary || plan.reason || "Route facts below come directly from the backend plan response."}</p></div>
      <div className="route-snapshot-grid"><RouteSnapshot label="Before · original route" route={original} byId={byId} tone="before" /><div className="route-transition">→</div><RouteSnapshot label="After · selected route" route={selected} byId={byId} tone="after" /></div>
      {candidates.length > 0 ? <div className="alternative-route-list"><div className="alternative-route-heading"><strong>Available alternatives ({candidates.length})</strong><span>Compared by backend score, time, cost, risk, and capacity</span></div>{candidates.map((route, index) => { const durationDelta = route.duration_hours - (original?.duration_hours || route.duration_hours); const costDelta = route.cost - (original?.cost || route.cost); return <div className={`alternative-route ${route === selected || index === 0 ? "selected" : ""}`} key={`${route.route_ids.join("-")}-${index}`}><div className="alternative-route-title"><strong>{route === selected || index === 0 ? "Selected route" : `Alternative ${index + 1}`}</strong>{route === selected || index === 0 ? <StatusPill tone="success">Recommended</StatusPill> : <StatusPill tone="info">Candidate</StatusPill>}</div><p>{route.location_ids.map((id) => locationLabel(id, byId)).join(" → ")}</p><div className="alternative-route-stats"><span>Duration <b>{formatNumber(route.duration_hours)} h ({durationDelta >= 0 ? "+" : ""}{formatNumber(durationDelta)} h)</b></span><span>Cost <b>{formatMoney(route.cost)} ({costDelta >= 0 ? "+" : ""}{formatMoney(costDelta)})</b></span><span>Risk <b>{formatPercent(route.risk_score)}</b></span><span>Capacity <b>{route.capacity_feasible ? "Feasible" : "Over capacity"}</b></span></div></div>; })}</div> : <div className="no-route-alert"><strong>No other ways available</strong><p>{plan.reason || "The original route is disrupted and no capacity-feasible alternative was found."}</p></div>}
    </Panel>
  );
}

function ShipmentWorkspace({ shipments, recommendations, byId, batch, onAnalytics, analytics, working }) {
  const [search, setSearch] = useState("");
  const [priority, setPriority] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [sort, setSort] = useState("id");
  const [selectedId, setSelectedId] = useState(null);
  const recommendationById = Object.fromEntries((recommendations || []).map((item) => [item.shipment_id, item]));
  const rows = shipments.filter((shipment) => {
    const recommendation = recommendationById[shipment.id];
    const statusMatches = status === "ALL" || recommendation?.status === status;
    return (!search || `${shipment.id} ${locationLabel(shipment.destination_id, byId)}`.toLowerCase().includes(search.toLowerCase())) && (priority === "ALL" || shipment.priority === priority) && statusMatches;
  }).sort((a, b) => {
    if (sort === "priority") return a.priority.localeCompare(b.priority);
    if (sort === "destination") return locationLabel(a.destination_id, byId).localeCompare(locationLabel(b.destination_id, byId));
    return a.id.localeCompare(b.id);
  }).slice(0, 12);
  const selected = selectedId ? shipments.find((shipment) => shipment.id === selectedId) : null;
  const selectedRecommendation = selected ? recommendationById[selected.id] : null;
  return (
    <Panel id="shipments" className="shipments-panel">
      <PanelHeader title="Affected Shipments · Reroute Queue" action={<button className="text-button">View all</button>} />
      <div className="filters"><input aria-label="Search shipments" placeholder="Search shipment or destination" value={search} onChange={(event) => setSearch(event.target.value)} /><select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="ALL">All priorities</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="ALL">All reroute results</option>{REROUTE_QUEUE_RESULT_OPTIONS.map((option) => <option value={option} key={option}>{titleCase(option)}</option>)}</select><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="id">Sort: ID</option><option value="priority">Sort: priority</option><option value="destination">Sort: destination</option></select></div>
      {!rows.length ? <p className="empty-state">No shipments match these filters.</p> : <div className="table-scroll"><table className="shipment-table"><thead><tr><th>Shipment ID</th><th>Origin</th><th>Destination</th><th>Status</th><th>Priority</th><th>Delay</th><th /></tr></thead><tbody>{rows.map((shipment) => { const recommendation = recommendationById[shipment.id]; const rowStatus = shipment.status; const isAffected = true; return <tr key={shipment.id} className={selectedId === shipment.id ? "selected-row" : ""} onClick={() => setSelectedId(shipment.id)}><td><strong>{shipment.id}</strong></td><td>{locationLabel(shipment.origin_id, byId)}</td><td>{locationLabel(shipment.destination_id, byId)}</td><td><StatusPill tone={recommendation?.status === "REROUTED" ? "success" : isAffected ? "danger" : "neutral"}>{titleCase(rowStatus)}</StatusPill>{recommendation && <small>Reroute: {titleCase(recommendation.status)}</small>}</td><td>{shipment.priority}</td><td>{recommendation ? `${formatNumber(recommendation.delay_saved_hours)} h` : "—"}</td><td><button className="icon-button" onClick={(event) => { event.stopPropagation(); setSelectedId(shipment.id); }}>›</button></td></tr>; })}</tbody></table></div>}
      {selected && <div className="shipment-detail"><div><div className="detail-title"><strong>{selected.id}</strong><StatusPill tone={selectedRecommendation?.status === "REROUTED" ? "success" : "warning"}>{titleCase(selected.status)}</StatusPill></div><p>{locationLabel(selected.origin_id, byId)} → {locationLabel(selected.destination_id, byId)}</p><small>Priority {selected.priority} · Load {selected.load_units} units{selectedRecommendation ? ` · Reroute: ${titleCase(selectedRecommendation.status)}` : ""}</small></div>{selectedRecommendation ? <div className="detail-metrics"><span>Delay saved <b>{formatNumber(selectedRecommendation.delay_saved_hours)} h</b></span><span>Additional cost <b>{formatMoney(selectedRecommendation.additional_cost)}</b></span><span>Risk <b>{formatPercent(selectedRecommendation.selected_route?.risk_score)}</b></span><button className="secondary small" disabled={!batch || working} onClick={() => onAnalytics(selected.id)}>{analytics[selected.id] ? "Refresh analysis" : "Analyze shipment"}</button></div> : <p className="muted-text">Run the selected disruption to generate a recommendation for this shipment.</p>}</div>}
      {selected && selectedRecommendation && analytics[selected.id] && <ShipmentAnalysis shipment={selected} recommendation={selectedRecommendation} analysis={analytics[selected.id]} byId={byId} />}
    </Panel>
  );
}

function ReroutingSummary({ batch, byId, plan, disruption }) {
  const recommendations = batch?.recommendations || [];
  const groups = {};
  recommendations.filter((item) => item.selected_route).forEach((item) => {
    const port = item.selected_route.location_ids.find((id) => byId[id]?.type === "PORT") || "Other routes";
    groups[port] = (groups[port] || 0) + 1;
  });
  const entries = Object.entries(groups).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;
  let offset = 0;
  const colors = ["#2cd68b", "#398cf5", "#ffae42", "#a67af7"];
  const segments = entries.map(([, count], index) => { const start = offset; offset += (count / total) * 100; return `${colors[index % colors.length]} ${start}% ${offset}%`; });
  const insights = [];
  if (batch) insights.push(`${batch.metrics.successfully_rerouted} shipments rerouted successfully in the latest simulation.`);
  if (disruption) insights.push(`${titleCase(disruption.disruption_type)} affects ${disruption.affected_location_ids?.map((id) => locationLabel(id, byId)).join(", ") || "selected route legs"}.`);
  if (plan?.selected_route) insights.push(`The selected alternative has ${formatPercent(plan.selected_route.risk_score)} average leg risk and ${formatPercent(plan.selected_route.capacity_penalty)} capacity pressure.`);
  if (!insights.length) insights.push("Run a scenario to generate grounded operational insights.");
  return (
    <Panel className="summary-panel">
      <PanelHeader title="Rerouting Summary" action={<button className="text-button">View all</button>} />
      {!batch ? <p className="muted-text">Run an affected-shipment batch to populate rerouting distribution.</p> : <div className="summary-content"><div className="donut" style={{ background: `conic-gradient(${segments.join(",")})` }}><div><strong>{batch.metrics.successfully_rerouted}</strong><span>Rerouted</span></div></div><div className="summary-legend">{entries.map(([id, count], index) => <div key={id}><i style={{ background: colors[index % colors.length] }} /><span>Via {locationLabel(id, byId)}</span><b>{count} ({formatNumber((count / total) * 100, 1)}%)</b></div>)}</div></div>}
      <div className="summary-insights"><ul className="insights-list">{insights.map((insight) => <li key={insight}>{insight}</li>)}</ul><small className="muted-text">Generated from current backend decision data</small></div>
    </Panel>
  );
}

function CapacityPanel({ routes, byId }) {
  const bottlenecks = [...routes].sort((a, b) => routeUtilization(b) - routeUtilization(a)).slice(0, 5);
  return <Panel className="capacity-panel"><PanelHeader title="Capacity Utilization" action={<StatusPill tone="info">Backend values</StatusPill>} /><div className="capacity-list">{bottlenecks.map((route) => { const utilization = routeUtilization(route); const blocked = route.status === "BLOCKED"; return <div className="capacity-row" key={route.id}><div className="capacity-label"><strong>{route.id} · {locationLabel(route.source_location_id, byId)} → {locationLabel(route.destination_location_id, byId)}</strong><small>{route.mode} · {route.current_load}/{route.capacity} units</small></div><div className="capacity-bar"><span className={blocked ? "blocked" : utilization >= .85 ? "critical" : utilization >= .6 ? "high" : "normal"} style={{ width: `${Math.min(utilization * 100, 100)}%` }} /></div><strong className={blocked ? "danger-text" : ""}>{blocked ? "Blocked" : formatPercent(utilization)}</strong></div>; })}</div></Panel>;
}

function RiskCustomers({ shipments, recommendations, byId }) {
  const recommendationById = Object.fromEntries((recommendations || []).map((item) => [item.shipment_id, item]));
  const grouped = {};
  shipments.forEach((shipment) => {
    const recommendation = recommendationById[shipment.id];
    const risk = recommendation?.selected_route?.risk_score || (shipment.priority === "HIGH" ? 0.7 : shipment.priority === "MEDIUM" ? 0.45 : 0.2);
    const key = shipment.destination_id;
    grouped[key] ||= { count: 0, risk: 0 };
    grouped[key].count += 1;
    grouped[key].risk = Math.max(grouped[key].risk, risk);
  });
  const rows = Object.entries(grouped).sort((a, b) => b[1].risk - a[1].risk).slice(0, 5);
  return <Panel><PanelHeader title="Top At-Risk Customers" action={<button className="text-button">View all</button>} /><div className="risk-list">{rows.map(([id, item]) => <div className="risk-row" key={id}><span>{locationLabel(id, byId)}</span><small>{item.count} shipments</small><StatusPill tone={item.risk >= .6 ? "danger" : item.risk >= .35 ? "warning" : "success"}>{item.risk >= .6 ? "High" : item.risk >= .35 ? "Medium" : "Low"}</StatusPill></div>)}</div></Panel>;
}

function HistoryPanel({ history, compareIds, setCompareIds, onOpen, onExport }) {
  const compare = (id) => setCompareIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id].slice(-3));
  return <Panel id="history" className="history-panel"><PanelHeader title="Scenario History & Comparison" action={<div className="header-actions"><button className="secondary small" onClick={() => onExport("json")}>Export JSON</button><button className="secondary small" onClick={() => onExport("csv")}>Export CSV</button></div>} />{!history.length ? <p className="muted-text">No persisted simulations yet.</p> : <div className="table-scroll"><table><thead><tr><th>Compare</th><th>Scenario</th><th>Created</th><th>Affected</th><th>Rerouted</th><th>Delay saved</th><th /></tr></thead><tbody>{history.slice(-8).reverse().map((run) => { const metrics = run.results?.metrics; const scenario = run.disruption; return <tr key={run.id} className={compareIds.includes(run.id) ? "selected-row" : ""}><td><input type="checkbox" checked={compareIds.includes(run.id)} onChange={() => compare(run.id)} /></td><td><strong>{titleCase(scenario?.disruption_type || "Stored run")}</strong><small>{scenario?.description || run.id.slice(0, 8)}</small></td><td>{new Date(run.created_at).toLocaleString()}</td><td>{metrics?.affected_shipments ?? "—"}</td><td>{metrics?.successfully_rerouted ?? "—"}</td><td>{metrics ? `${formatNumber(metrics.average_delay_saved_hours)} h` : "Not rerouted"}</td><td><button className="text-button" onClick={() => onOpen(run)}>Open</button></td></tr>; })}</tbody></table></div>}{compareIds.length > 1 && <div className="comparison-strip"><strong>Comparing {compareIds.length} stored runs</strong>{compareIds.map((id) => { const run = history.find((item) => item.id === id); return <span key={id}>{titleCase(run?.disruption?.disruption_type || "Run")} · {run?.results?.metrics?.reroute_success_rate != null ? formatPercent(run.results.metrics.reroute_success_rate) : "Pending"}</span>; })}</div>}</Panel>;
}

function RoutePlanner({ locations, destinations, byId, origin, setOrigin, destination, setDestination, priority, setPriority, loadUnits, setLoadUnits, onSubmit, working }) {
  return (
    <div className="planner-strip" id="recommendation">
      <PanelHeader eyebrow="Decision workspace" title="Plan an interactive route" action={<StatusPill tone="info">Source of truth: API</StatusPill>} />
      <form onSubmit={onSubmit} className="planner-form">
        <label>Origin<select value={origin} onChange={(event) => setOrigin(event.target.value)}>{locations.filter((item) => item.type !== "CUSTOMER").map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
        <label>Destination<select value={destination} onChange={(event) => setDestination(event.target.value)}>{destinations.map((id) => <option value={id} key={id}>{locationLabel(id, byId)}</option>)}</select></label>
        <label>Priority<select value={priority} onChange={(event) => setPriority(event.target.value)}><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select></label>
        <label>Load units<input type="number" min="1" max="100" value={loadUnits} onChange={(event) => setLoadUnits(event.target.value)} /></label>
        <button className="primary" disabled={working || !origin || !destination}>{working ? "Planning..." : "Plan route →"}</button>
      </form>
    </div>
  );
}

export default function App() {
  const [locations, setLocations] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [shipments, setShipments] = useState([]);
  const [scenarios, setScenarios] = useState({});
  const [history, setHistory] = useState([]);
  const [activeView, setActiveView] = useState("overview");
  const [selectedDisruptionKeys, setSelectedDisruptionKeys] = useState(["singapore_closure"]);
  const [appliedDisruption, setAppliedDisruption] = useState(null);
  const [customDisruption, setCustomDisruption] = useState(null);
  const [customOpen, setCustomOpen] = useState(false);
  const [customForm, setCustomForm] = useState({ disruption_type: "PORT_CLOSURE", affected_location_ids: [], affected_route_ids: [], duration_hours: 72, severity: "HIGH", description: "" });
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [priority, setPriority] = useState("MEDIUM");
  const [loadUnits, setLoadUnits] = useState(10);
  const [plan, setPlan] = useState(null);
  const [batch, setBatch] = useState(null);
  const [analytics, setAnalytics] = useState({});
  const [layers, setLayers] = useState({ locations: true, routes: true, capacity: true });
  const [compareIds, setCompareIds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [chatMessages, setChatMessages] = useState([]);
  const [chatQuestion, setChatQuestion] = useState("");
  const [chatWorking, setChatWorking] = useState(false);

  async function loadDashboard() {
    setLoading(true);
    setError("");
    try {
      const [loadedLocations, loadedRoutes, loadedShipments, loadedScenarios, loadedHistory] = await Promise.all([api("/locations"), api("/routes"), api("/shipments"), api("/disruptions"), api("/recommendations")]);
      setLocations(loadedLocations); setRoutes(loadedRoutes); setShipments(loadedShipments); setScenarios(loadedScenarios); setHistory(loadedHistory); setLastUpdated(new Date());
      const factory = loadedLocations.find((item) => item.type === "FACTORY");
      if (factory) setOrigin((current) => current || factory.id);
    } catch (reason) { setError(reason.message); } finally { setLoading(false); }
  }

  useEffect(() => { loadDashboard(); }, []);

  const byId = useMemo(() => Object.fromEntries(locations.map((item) => [item.id, item])), [locations]);
  const destinations = useMemo(() => {
    const adjacency = {};
    routes.forEach((route) => { adjacency[route.source_location_id] ||= []; adjacency[route.source_location_id].push(route.destination_location_id); });
    const seen = new Set([origin]); const pending = [origin];
    while (pending.length) { const current = pending.pop(); (adjacency[current] || []).forEach((next) => { if (!seen.has(next)) { seen.add(next); pending.push(next); } }); }
    seen.delete(origin);
    return [...seen].sort((a, b) => locationLabel(a, byId).localeCompare(locationLabel(b, byId)));
  }, [origin, routes, byId]);
  useEffect(() => { if (!destinations.includes(destination)) setDestination(destinations.find((id) => byId[id]?.type === "CUSTOMER") || destinations[0] || ""); }, [destinations, destination, byId]);

  const selectedDisruptions = useMemo(() => selectedDisruptionKeys.map((key) => key === "custom" ? customDisruption : scenarios[key]).filter(Boolean), [selectedDisruptionKeys, customDisruption, scenarios]);
  const selectedDisruption = useMemo(() => combineDisruptions(selectedDisruptions), [selectedDisruptions]);
  const activeDisruption = appliedDisruption;
  const activeAffected = useMemo(() => {
    const affectedIds = new Set(
      (batch?.recommendations || [])
        .filter((recommendation) => REROUTE_QUEUE_RESULTS.has(recommendation.status))
        .map((recommendation) => recommendation.shipment_id),
    );
    return shipments.filter((shipment) => (
      affectedIds.has(shipment.id)
      && !INACTIVE_SHIPMENT_STATUSES.has(String(shipment.status).toUpperCase())
    ));
  }, [shipments, batch]);
  const displayedRecommendations = batch?.recommendations || [];
  const assistantContext = useMemo(() => ({
    plan,
    disruption: activeDisruption,
    affected_shipments: activeAffected,
    recommendations: displayedRecommendations,
    locations: Object.fromEntries(locations.map((location) => [location.id, location.name])),
  }), [plan, activeDisruption, activeAffected, displayedRecommendations, locations]);
  const kpis = {
    disrupted: activeAffected.length,
    customers: new Set(activeAffected.map((shipment) => shipment.destination_id)).size,
    rerouted: batch?.metrics?.successfully_rerouted || 0,
    delay: batch?.metrics?.average_delay_saved_hours || 0,
    cost: batch?.metrics?.total_additional_cost || 0,
  };

  function navigate(view) {
    setActiveView(view);
    const target = document.getElementById(view === "overview" ? "overview" : view === "recommendation" ? "recommendation" : view);
    if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function toggleDisruption(key) {
    setSelectedDisruptionKeys((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  }

  async function planRoute(event) {
    event.preventDefault();
    setWorking(true); setError("");
    try {
      const disruption = activeDisruption ? { ...activeDisruption, duration_hours: Number(activeDisruption.duration_hours) } : null;
      const result = await api("/plan-route", { method: "POST", body: JSON.stringify({ origin_id: origin, destination_id: destination, priority, load_units: Number(loadUnits), disruption, generate_explanation: true }) });
      setPlan(result);
      navigate("recommendation");
    } catch (reason) { setError(reason.message); } finally { setWorking(false); }
  }

  async function runBatch(disruption = selectedDisruption) {
    if (!disruption || (!(disruption.affected_location_ids || []).length && !(disruption.affected_route_ids || []).length)) { setError("Select at least one affected location or route before running a simulation."); return; }
    setWorking(true); setError("");
    try {
      const simulation = await api("/simulate-disruption", { method: "POST", body: JSON.stringify(disruption) });
      const result = await api(`/reroute?disruption_id=${encodeURIComponent(simulation.disruption_id)}`, { method: "POST" });
      setAppliedDisruption(disruption);
      setPlan(null);
      setAnalytics({});
      setBatch({ ...result, simulation });
      const loadedHistory = await api("/recommendations");
      setHistory(loadedHistory); setLastUpdated(new Date());
      navigate("shipments");
    } catch (reason) { setError(reason.message); } finally { setWorking(false); }
  }

  async function createCustom(event) {
    event.preventDefault();
    if (!(customForm.affected_location_ids.length || customForm.affected_route_ids.length)) { setError("Choose at least one affected location or route."); return; }
    const custom = { ...customForm, duration_hours: Number(customForm.duration_hours) };
    setCustomDisruption(custom); setSelectedDisruptionKeys((current) => current.includes("custom") ? current : [...current, "custom"]); setCustomOpen(false); setError("");
  }

  async function loadAnalytics(shipmentId) {
    if (!batch) return;
    setWorking(true); setError("");
    try { const result = await api("/shipment-analytics", { method: "POST", body: JSON.stringify({ disruption_id: batch.disruption_id, shipment_id: shipmentId }) }); setAnalytics((current) => ({ ...current, [shipmentId]: result.analytics })); } catch (reason) { setError(reason.message); } finally { setWorking(false); }
  }

  async function askAssistant(event) {
    event.preventDefault();
    const question = chatQuestion.trim();
    if (!question) return;
    setChatQuestion("");
    setChatMessages((current) => [...current, { role: "user", text: question }]);
    setChatWorking(true);
    try {
      const result = await api("/assistant", { method: "POST", body: JSON.stringify({
        question,
        simulation_run_id: batch?.disruption_id || null,
        context: assistantContext,
      }) });
      const evidence = result.evidence?.length ? `\nEvidence: ${result.evidence.join(" · ")}` : "";
      setChatMessages((current) => [...current, { role: "assistant", text: `${result.answer}${evidence}`, source: result.source }]);
    } catch (reason) {
      setChatMessages((current) => [...current, { role: "assistant", text: `I could not answer that from the current dashboard context: ${reason.message}` }]);
    } finally { setChatWorking(false); }
  }

  function openHistory(run) {
    const disruption = run.disruption;
    if (!disruption) { setError("This legacy run has no structured disruption inputs to reopen."); return; }
    const matchingKey = Object.keys(scenarios).find((key) => JSON.stringify(scenarios[key]) === JSON.stringify(disruption));
    if (matchingKey) setSelectedDisruptionKeys([matchingKey]);
    else { setCustomDisruption(disruption); setSelectedDisruptionKeys(["custom"]); }
    setAppliedDisruption(disruption);
    if (run.results?.recommendations) setBatch({ ...run.results, disruption_id: run.id });
    navigate("overview");
  }

  function exportHistory(format) {
    const selected = history.filter((run) => !compareIds.length || compareIds.includes(run.id));
    const rows = selected.map((run) => ({ scenario_id: run.id, created_at: run.created_at, disruption_type: run.disruption?.disruption_type || "UNKNOWN", affected_shipments: run.results?.metrics?.affected_shipments ?? null, successfully_rerouted: run.results?.metrics?.successfully_rerouted ?? null, average_delay_saved_hours: run.results?.metrics?.average_delay_saved_hours ?? null, total_additional_cost: run.results?.metrics?.total_additional_cost ?? null }));
    const content = format === "json" ? JSON.stringify(rows, null, 2) : [Object.keys(rows[0] || { scenario_id: "" }).join(","), ...rows.map((row) => Object.values(row).map((value) => JSON.stringify(value ?? "")).join(","))].join("\n");
    const blob = new Blob([content], { type: format === "json" ? "application/json" : "text/csv" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `reroute-comparison.${format}`; link.click(); URL.revokeObjectURL(link.href);
  }

  if (loading) return <div className="loading-screen"><div className="brand-mark">◉</div><p>Loading supply chain command center...</p></div>;

  return (
    <div className="app-shell">
      <Sidebar activeView={activeView} onNavigate={navigate} />
      <main className="dashboard" id="overview">
        <header className="topbar"><div><p className="breadcrumb">Operations / Command Center</p><h1>Supply Chain Rerouting Dashboard</h1><p className="subtitle">Real-time visibility. AI-assisted decisions. Resilient supply chain.</p></div><div className="topbar-actions"><span className="last-updated">Last updated: {formatNumber((Date.now() - lastUpdated.getTime()) / 60000, 0)} min ago <button className="refresh-button" onClick={loadDashboard}>↻</button></span><button className="date-button">▣ {new Date().toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}⌄</button><button className="profile-button"><span>◉</span> Operations Manager</button></div></header>
        {error && <div className="error-banner">{error}<button onClick={() => setError("")}>×</button></div>}
        <section className="kpi-grid"><KpiCard icon="▣" label="Total Shipments" value={formatNumber(shipments.length, 0)} delta="↑ 12.5%" note="vs yesterday" tone="blue" /><KpiCard icon="!" label="Disrupted Shipments" value={formatNumber(kpis.disrupted, 0)} delta={kpis.disrupted ? "↑ Active" : "— None"} note="current scenario" tone="red" /><KpiCard icon="♟" label="Affected Customers" value={formatNumber(kpis.customers, 0)} delta={kpis.customers ? "↑ Active" : "— None"} note="current scenario" tone="orange" /><KpiCard icon="↪" label="Rerouted Shipments" value={formatNumber(kpis.rerouted, 0)} delta={batch ? `↑ ${formatPercent(batch.metrics.reroute_success_rate)}` : "— Pending"} note="success rate" tone="green" /><KpiCard icon="◷" label="Avg. Delay Avoided" value={batch ? `${formatNumber(kpis.delay)} h` : "—"} delta={batch ? "↑ Saved" : "— Pending"} note="latest batch" tone="purple" /><KpiCard icon="$" label="Est. Cost Impact" value={batch ? formatMoney(kpis.cost) : "—"} delta={batch ? "↑" : "— Pending"} note="latest batch" tone="blue" /></section>
        <RoutePlanner locations={locations} destinations={destinations} byId={byId} origin={origin} setOrigin={setOrigin} destination={destination} setDestination={setDestination} priority={priority} setPriority={setPriority} loadUnits={loadUnits} setLoadUnits={setLoadUnits} onSubmit={planRoute} working={working} />
        <div className="recommendation-under-planner"><RouteComparison plan={plan} byId={byId} /></div>
        <div className="main-grid"><Panel id="network" className="map-panel"><PanelHeader eyebrow="Network monitoring" title="Supply Chain Network Map" action={<div className="map-layers">{Object.entries(layers).map(([key, value]) => <label key={key}><input type="checkbox" checked={value} onChange={(event) => setLayers((current) => ({ ...current, [key]: event.target.checked }))} /> {titleCase(key)}</label>)}</div>} /><NetworkMap locations={locations} routes={routes} plan={plan} disruption={activeDisruption} layers={layers} /></Panel><ReroutingSummary batch={batch} byId={byId} plan={plan} disruption={activeDisruption} /></div>
        <div className="content-grid three"><DisruptionPanel scenarios={scenarios} selectedKeys={selectedDisruptionKeys} onSelect={toggleDisruption} onRun={() => runBatch()} customScenario={customDisruption} customOpen={customOpen} setCustomOpen={setCustomOpen} custom={customForm} setCustom={setCustomForm} locations={locations} routes={routes} byId={byId} onCustomSubmit={createCustom} working={working} /><ShipmentWorkspace shipments={activeAffected} recommendations={displayedRecommendations} byId={byId} batch={batch} onAnalytics={loadAnalytics} analytics={analytics} working={working} /><AssistantPanel plan={plan} byId={byId} disruption={activeDisruption} messages={chatMessages} question={chatQuestion} setQuestion={setChatQuestion} onAsk={askAssistant} chatWorking={chatWorking} /></div>
        <div className="content-grid two"><CapacityPanel routes={routes} byId={byId} /><RiskCustomers shipments={activeAffected} recommendations={displayedRecommendations} byId={byId} /></div>
        <HistoryPanel history={history} compareIds={compareIds} setCompareIds={setCompareIds} onOpen={openHistory} onExport={exportHistory} />
        <footer><span>SC-Reroute · deterministic routing remains backend-owned</span><span>Local MVP · API {API_URL}</span></footer>
      </main>
    </div>
  );
}
