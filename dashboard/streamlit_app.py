import os
import requests
import streamlit as st
import plotly.graph_objects as go

API_URL=os.getenv("API_URL","http://localhost:8000")
st.set_page_config(page_title="Supply Chain Reroute Agent",layout="wide")
st.title("Autonomous Supply Chain Reroute Agent")

def api(path, method="get", timeout=30, **kwargs):
    response=getattr(requests,method)(f"{API_URL}{path}",timeout=timeout,**kwargs)
    response.raise_for_status(); return response.json()

try:
    locations=api("/locations"); routes=api("/routes"); scenarios=api("/disruptions")
except requests.RequestException as exc:
    st.error(f"Backend unavailable: {exc}"); st.stop()

by_id={x["id"]:x for x in locations}
plan=st.session_state.get("plan")


def reachable_locations(origin_id):
    """Return destinations reachable on the directed base network."""
    adjacency={location_id: [] for location_id in by_id}
    for route in routes: adjacency[route["source_location_id"]].append(route["destination_location_id"])
    seen={origin_id}; pending=[origin_id]
    while pending:
        current=pending.pop()
        for destination_id in adjacency.get(current,[]):
            if destination_id not in seen:
                seen.add(destination_id); pending.append(destination_id)
    return seen-{origin_id}


left,right=st.columns([1,2])
with left:
    st.subheader("Plan a route")
    location_names={x["id"]:f"{x['name']} ({x['type'].title()})" for x in locations}
    origin=st.selectbox("Origin",list(location_names),format_func=location_names.get,index=0)
    reachable=reachable_locations(origin)
    available_destinations=sorted(reachable,key=lambda location_id: (by_id[location_id]["type"] != "CUSTOMER",location_names[location_id]))
    destination=st.selectbox("Destination",available_destinations,format_func=location_names.get,help="Only destinations reachable from this origin on the current directed network are shown.")
    priority=st.selectbox("Priority",["HIGH","MEDIUM","LOW"],index=1)
    load_units=st.number_input("Shipment load units",1,100,10)
    st.subheader("Disruption simulation")
    use_disruption=st.toggle("Apply a disruption",value=True)
    key=st.selectbox("Disruption scenario",list(scenarios),format_func=lambda x:x.replace("_"," ").title())
    disruption=dict(scenarios[key])
    disruption["duration_hours"]=st.number_input("Duration (hours)",1,720,int(disruption["duration_hours"]))
    if st.button("Plan and reroute",type="primary"):
        try:
            payload={"origin_id":origin,"destination_id":destination,"priority":priority,"load_units":load_units,"disruption":disruption if use_disruption else None}
            with st.spinner("Calculating routes and generating grounded analysis..."):
                st.session_state.plan=api("/plan-route","post",json=payload,timeout=90)
            st.rerun()
        except requests.RequestException as exc: st.error(str(exc))
with right:
    fig=go.Figure()
    for route in routes:
        a,b=by_id[route["source_location_id"]],by_id[route["destination_location_id"]]
        fig.add_trace(go.Scattergeo(lon=[a["longitude"],b["longitude"]],lat=[a["latitude"],b["latitude"]],mode="lines",line={"width":1,"color":"#9ca3af"},hoverinfo="skip",showlegend=False))
    disrupted=set(disruption.get("affected_location_ids",[])) if use_disruption else set()
    def draw_path(route, color, label, width=4):
        if not route: return
        nodes=route["location_ids"]
        fig.add_trace(go.Scattergeo(lon=[by_id[node]["longitude"] for node in nodes],lat=[by_id[node]["latitude"] for node in nodes],mode="lines",line={"width":width,"color":color},name=label))
    if plan:
        draw_path(plan.get("original_route"),"#2563eb","Original route")
        for number,route in enumerate(plan.get("candidate_routes",[]),start=1):
            draw_path(route,["#16a34a","#f59e0b","#9333ea"][number-1],f"Candidate {number}",5 if route==plan.get("selected_route") else 2)
    fig.add_trace(go.Scattergeo(lon=[x["longitude"] for x in locations],lat=[x["latitude"] for x in locations],text=[f"{x['name']}" + (" — disruption" if x['id'] in disrupted else "") for x in locations],mode="markers+text",textposition="top center",marker={"size":10,"color":["#dc2626" if x["id"] in disrupted else "#2563eb" for x in locations]}))
    fig.update_geos(showland=True,landcolor="#f3f4f6",fitbounds="locations"); fig.update_layout(height=420,margin={"l":0,"r":0,"t":0,"b":0}); st.plotly_chart(fig,use_container_width=True)

if plan:
    st.subheader("Route plan")
    if plan["status"]!="ROUTE_FOUND":
        st.error(plan.get("reason") or "No feasible route was found.")
        st.caption("Try another disruption, reduce the load units, choose a different reachable destination, or switch off disruption simulation.")
    else:
        st.success("Deterministic recommended route found.")
        st.caption("Original route is blue; the selected candidate is green; other candidates are orange or purple; disruption nodes are red.")
        st.dataframe(plan["candidate_routes"],use_container_width=True)
        st.subheader("Grounded GPT analysis")
        st.json(plan.get("explanation") or {})

    if plan.get("disruption"):
        st.divider()
        st.subheader("Affected shipment rerouting")
        if st.button("Show all affected shipments",key="show_batch"):
            try:
                with st.spinner("Calculating affected shipments and deterministic reroutes..."):
                    simulation=api("/simulate-disruption","post",json=plan["disruption"])
                    st.session_state.batch=api(f"/reroute?disruption_id={simulation['disruption_id']}","post",timeout=30)
                    st.session_state.shipment_analytics={}
            except requests.RequestException as exc: st.error(f"Batch reroute failed: {exc}")

batch=st.session_state.get("batch")
if batch:
    st.caption(f"Affected: {batch['metrics']['affected_shipments']} · Successfully rerouted: {batch['metrics']['successfully_rerouted']} · Success rate: {batch['metrics']['reroute_success_rate']:.0%}")
    analytics=st.session_state.setdefault("shipment_analytics",{})
    for recommendation in batch["recommendations"]:
        shipment_id=recommendation["shipment_id"]
        with st.expander(f"{shipment_id} — {recommendation['status']}"):
            if recommendation.get("selected_route"):
                st.write("Recommended route:"," → ".join(recommendation["selected_route"]["location_ids"]))
                st.dataframe(recommendation.get("candidate_routes",[]),use_container_width=True)
            else:
                st.warning("No route satisfies the current disruption and capacity constraints.")
            if st.button("Get GPT impact analytics",key=f"analytics_{batch['disruption_id']}_{shipment_id}"):
                try:
                    with st.spinner(f"Analysing {shipment_id}..."):
                        response=api("/shipment-analytics","post",json={"disruption_id":batch["disruption_id"],"shipment_id":shipment_id},timeout=90)
                        analytics[shipment_id]=response["analytics"]
                except requests.RequestException as exc: st.error(f"Analytics failed: {exc}")
            if shipment_id in analytics:
                st.subheader("Grounded shipment impact analysis")
                st.json(analytics[shipment_id])
