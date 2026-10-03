"""
Traffic Network representation using NetworkX.

Builds a weighted directed graph from the CityFlow road/intersection database.
Each node is an intersection, each edge is a road with attributes:
  - capacity, current_flow, length_km, speed_limit, lanes
"""

import networkx as nx
from sqlalchemy.orm import Session

from app.models import Road, Intersection


def build_network(db: Session) -> nx.DiGraph:
    """
    Build a NetworkX directed graph from the database.
    Returns the graph with roads as edges and intersections as nodes.
    """
    G = nx.DiGraph()

    # Add intersection nodes
    intersections = db.query(Intersection).all()
    for i in intersections:
        G.add_node(i.id, name=i.name, lat=i.latitude, lng=i.longitude, type=i.intersection_type)

    # Add road edges (bidirectional for traffic flow)
    roads = db.query(Road).all()
    for r in roads:
        attrs = {
            "road_id": r.id,
            "name": r.name,
            "capacity": r.capacity,
            "current_flow": r.current_flow,
            "length_km": r.length_km,
            "speed_limit": r.speed_limit,
            "lanes": r.lanes,
            "road_type": r.road_type,
            # Weight for shortest path = travel time (hours)
            "weight": r.length_km / r.speed_limit if r.speed_limit > 0 else float("inf"),
        }
        # Add both directions (bidirectional roads)
        G.add_edge(r.from_intersection, r.to_intersection, **attrs)
        G.add_edge(r.to_intersection, r.from_intersection, **attrs)

    return G


def get_road_attrs(G: nx.DiGraph, road_id: str) -> dict | None:
    """Find edge attributes by road_id."""
    for u, v, data in G.edges(data=True):
        if data.get("road_id") == road_id:
            return {"from": u, "to": v, **data}
    return None


def get_all_road_attrs(G: nx.DiGraph) -> dict[str, dict]:
    """Get all road attributes indexed by road_id."""
    roads = {}
    for u, v, data in G.edges(data=True):
        rid = data.get("road_id")
        if rid and rid not in roads:
            roads[rid] = {"from": u, "to": v, **data}
    return roads
