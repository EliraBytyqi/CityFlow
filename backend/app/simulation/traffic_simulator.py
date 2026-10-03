"""
Traffic Simulator for CityFlow AI.

Core simulation engine that models traffic redistribution
when a road is partially or completely closed.

Uses NetworkX graph + congestion model + routing to calculate:
  - displaced vehicles
  - alternative route distribution
  - congestion changes
  - estimated delays
"""

import uuid
import networkx as nx
from sqlalchemy.orm import Session

from app.models import Road, Simulation, SimulationResult
from app.demo_data import _traffic_multiplier, get_hourly_flow_for_road
from app.simulation.traffic_network import build_network, get_road_attrs, get_all_road_attrs
from app.simulation.congestion import (
    calculate_utilization,
    classify_congestion,
    estimate_delay_percent,
)
from app.simulation.routing import find_alternative_routes, get_roads_on_path, calculate_route_cost


def _get_flow_at_hour(daily_flow: int, hour: int) -> int:
    """Scale daily flow to a specific hour using the traffic pattern."""
    total_mult = sum(_traffic_multiplier(h) for h in range(24))
    return int(daily_flow * _traffic_multiplier(hour) / total_mult)


def simulate_closure(
    db: Session,
    road_id: str,
    closure_percentage: int,
    simulation_hour: int = 8,
) -> dict:
    """
    Simulate the effect of closing a road (partially or fully).

    Args:
        db: Database session
        road_id: ID of the road to close
        closure_percentage: 0-100, where 100 = fully closed
        simulation_hour: Hour of day (0-23) for the simulation

    Returns:
        Complete simulation result dictionary
    """
    # Build network
    G = build_network(db)
    all_roads = get_all_road_attrs(G)

    # Find the target road
    target = all_roads.get(road_id)
    if not target:
        raise ValueError(f"Road not found: {road_id}")

    # Get hourly flow for the target road at the simulation hour
    hourly_flows = {}
    roads_db = db.query(Road).all()
    road_map = {r.id: r for r in roads_db}

    for rid, attrs in all_roads.items():
        daily = attrs["current_flow"]
        hourly_flows[rid] = _get_flow_at_hour(daily, simulation_hour)

    target_hourly_flow = hourly_flows.get(road_id, 0)

    # Calculate displaced vehicles
    displaced = int(target_hourly_flow * closure_percentage / 100)

    # Remaining capacity after closure
    remaining_capacity_pct = (100 - closure_percentage) / 100

    # Find alternative routes
    from_node = target["from"]
    to_node = target["to"]

    excluded = [(from_node, to_node), (to_node, from_node)] if closure_percentage == 100 else []

    alt_routes = find_alternative_routes(G, from_node, to_node, excluded_edges=excluded, k=5)

    # Also find routes in the reverse direction
    alt_routes_rev = find_alternative_routes(G, to_node, from_node, excluded_edges=excluded, k=5)

    # Collect all roads that appear in alternative routes
    alt_road_ids = set()
    for route in alt_routes + alt_routes_rev:
        for rid in get_roads_on_path(G, route):
            if rid != road_id:
                alt_road_ids.add(rid)

    # If no alternative routes found, spread to neighboring roads
    if not alt_road_ids:
        for neighbor in list(G.neighbors(from_node)) + list(G.neighbors(to_node)):
            for _, _, data in G.edges(neighbor, data=True):
                rid = data.get("road_id")
                if rid and rid != road_id:
                    alt_road_ids.add(rid)

    # Distribute displaced traffic to alternative roads
    # Weight by inverse of route cost (shorter routes get more traffic)
    route_weights = {}
    for route in alt_routes + alt_routes_rev:
        cost = calculate_route_cost(G, route)
        if cost > 0:
            for rid in get_roads_on_path(G, route):
                if rid != road_id and rid in alt_road_ids:
                    route_weights[rid] = route_weights.get(rid, 0) + (1.0 / cost)

    # Normalize weights and add roads without routes
    total_weight = sum(route_weights.values()) if route_weights else 1.0
    for rid in alt_road_ids:
        if rid not in route_weights:
            route_weights[rid] = 0.1 / total_weight  # Small share for peripheral roads

    total_weight = sum(route_weights.values())

    # Calculate redistribution
    affected_roads = []
    total_delay = 0.0

    for rid in alt_road_ids:
        if rid not in all_roads:
            continue

        road_attrs = all_roads[rid]
        before_flow = hourly_flows.get(rid, 0)
        road_cap = road_attrs["capacity"]
        hourly_cap = _get_flow_at_hour(road_cap, simulation_hour)
        if hourly_cap == 0:
            hourly_cap = int(road_cap * _traffic_multiplier(simulation_hour) /
                           sum(_traffic_multiplier(h) for h in range(24)))
            if hourly_cap == 0:
                hourly_cap = road_cap // 24

        # Calculate share of displaced traffic
        weight = route_weights.get(rid, 0)
        share = (weight / total_weight) if total_weight > 0 else 0
        added_flow = int(displaced * share)

        after_flow = before_flow + added_flow
        change_pct = ((after_flow - before_flow) / before_flow * 100) if before_flow > 0 else 0

        before_util = calculate_utilization(before_flow, hourly_cap)
        after_util = calculate_utilization(after_flow, hourly_cap)
        status = classify_congestion(after_util)

        delay = estimate_delay_percent(before_util, after_util, road_attrs.get("speed_limit", 50))
        total_delay += delay

        affected_roads.append({
            "road_id": rid,
            "road_name": road_attrs["name"],
            "before_flow": before_flow,
            "after_flow": after_flow,
            "change_percent": round(change_pct, 1),
            "capacity": hourly_cap,
            "utilization": round(after_util, 2),
            "status": status,
            "delay_percent": round(delay, 1),
        })

    # Also include the closed road itself
    target_hourly_cap = _get_flow_at_hour(target["capacity"], simulation_hour)
    if target_hourly_cap == 0:
        target_hourly_cap = target["capacity"] // 24

    closed_after_flow = int(target_hourly_flow * remaining_capacity_pct)
    closed_util = calculate_utilization(closed_after_flow, int(target_hourly_cap * remaining_capacity_pct)) if remaining_capacity_pct > 0 else 0.0

    affected_roads.insert(0, {
        "road_id": road_id,
        "road_name": target["name"],
        "before_flow": target_hourly_flow,
        "after_flow": closed_after_flow,
        "change_percent": -closure_percentage,
        "capacity": int(target_hourly_cap * remaining_capacity_pct),
        "utilization": round(closed_util, 2) if remaining_capacity_pct > 0 else 0.0,
        "status": "closed" if closure_percentage == 100 else classify_congestion(closed_util),
        "delay_percent": 0,
    })

    # Sort affected roads by change (descending)
    affected_roads_sorted = [affected_roads[0]] + sorted(
        affected_roads[1:], key=lambda x: x["change_percent"], reverse=True
    )

    # Calculate summary stats
    num_affected = len([r for r in affected_roads_sorted if r["road_id"] != road_id and r["change_percent"] > 0])
    num_critical = len([r for r in affected_roads_sorted if r["status"] == "critical"])
    avg_delay = round(total_delay / max(num_affected, 1), 1)

    # Generate explanation
    explanation = _generate_explanation(
        target["name"], closure_percentage, displaced,
        affected_roads_sorted, avg_delay, num_critical, simulation_hour
    )

    # Create simulation ID
    sim_id = f"sim_{uuid.uuid4().hex[:8]}"

    # Save to database
    sim = Simulation(
        id=sim_id,
        road_id=road_id,
        road_name=target["name"],
        closure_percentage=closure_percentage,
        simulation_hour=simulation_hour,
        displaced_vehicles=displaced,
        average_delay_percent=avg_delay,
        affected_roads_count=num_affected,
        critical_roads_count=num_critical,
        explanation=explanation,
        results_json={
            "roads": affected_roads_sorted,
            "displaced_vehicles": displaced,
            "average_delay_percent": avg_delay,
        },
    )
    db.add(sim)

    for road_data in affected_roads_sorted:
        db.add(SimulationResult(
            simulation_id=sim_id,
            road_id=road_data["road_id"],
            road_name=road_data["road_name"],
            before_flow=road_data["before_flow"],
            after_flow=road_data["after_flow"],
            change_percent=road_data["change_percent"],
            capacity=road_data["capacity"],
            utilization=road_data["utilization"],
            status=road_data["status"],
        ))

    db.commit()

    return {
        "simulation_id": sim_id,
        "closed_road": road_id,
        "closed_road_name": target["name"],
        "closure_percentage": closure_percentage,
        "simulation_hour": simulation_hour,
        "displaced_vehicles": displaced,
        "average_delay_percent": avg_delay,
        "affected_roads": num_affected,
        "critical_roads": num_critical,
        "roads": affected_roads_sorted,
        "explanation": explanation,
        "data_source": "simulated",
    }


def simulate_multi_closure(
    db: Session,
    roads: list[dict],
    simulation_hour: int = 8,
) -> dict:
    """
    Simulate closing multiple roads simultaneously.
    roads: [{"road_id": "road_01", "closure_percentage": 100}, ...]
    """
    # For multi-road closure, we run sequential simulations
    # and accumulate the effects
    G = build_network(db)
    all_roads_data = get_all_road_attrs(G)

    combined_results = []
    total_displaced = 0

    for road_spec in roads:
        result = simulate_closure(
            db,
            road_spec["road_id"],
            road_spec["closure_percentage"],
            simulation_hour,
        )
        total_displaced += result["displaced_vehicles"]
        combined_results.append(result)

    return {
        "simulations": combined_results,
        "total_displaced": total_displaced,
        "simulation_hour": simulation_hour,
    }


def _generate_explanation(
    road_name: str,
    closure_pct: int,
    displaced: int,
    affected_roads: list[dict],
    avg_delay: float,
    critical_count: int,
    hour: int,
) -> str:
    """
    Generate a natural-language explanation of simulation results.
    Uses ONLY the numerical simulation output—no invented data.
    """
    # Time period description
    if 7 <= hour <= 9:
        period = "morning peak"
    elif 16 <= hour <= 18:
        period = "evening peak"
    elif 10 <= hour <= 15:
        period = "midday"
    elif 20 <= hour or hour <= 5:
        period = "nighttime"
    else:
        period = f"{hour:02d}:00"

    closure_desc = "fully closing" if closure_pct == 100 else f"reducing capacity by {closure_pct}% on"

    # Find top affected roads (exclude the closed road)
    top_roads = [r for r in affected_roads if r["road_id"] != affected_roads[0]["road_id"]][:3]

    parts = [
        f"During the modeled {period} period, {closure_desc} {road_name} "
        f"displaces approximately {displaced:,} vehicles per hour."
    ]

    if top_roads:
        top_names = [r["road_name"] for r in top_roads]
        if len(top_names) == 1:
            parts.append(f"Traffic is primarily redirected to {top_names[0]}.")
        elif len(top_names) == 2:
            parts.append(f"Traffic is primarily redirected to {top_names[0]} and {top_names[1]}.")
        else:
            parts.append(
                f"Traffic is primarily redirected to {', '.join(top_names[:-1])}, "
                f"and {top_names[-1]}."
            )

        # Mention the most impacted road
        max_road = max(top_roads, key=lambda r: r["change_percent"])
        parts.append(
            f"{max_road['road_name']} receives the largest increase "
            f"({max_road['change_percent']:+.0f}%) because it provides "
            f"a relatively direct alternative route."
        )

    if critical_count > 0:
        parts.append(
            f"During this simulation, {critical_count} road{'s' if critical_count > 1 else ''} "
            f"{'exceed' if critical_count > 1 else 'exceeds'} the configured congestion threshold "
            f"(>90% utilization)."
        )

    if avg_delay > 0:
        parts.append(
            f"The average modeled delay across affected roads is approximately {avg_delay:.0f}%."
        )

    return " ".join(parts)
