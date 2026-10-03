"""
Routing module for CityFlow AI.

Finds alternative routes when a road is closed or capacity-reduced,
using NetworkX shortest-path algorithms.
"""

import networkx as nx
from typing import Optional


def find_alternative_routes(
    G: nx.DiGraph,
    from_node: str,
    to_node: str,
    excluded_edges: list[tuple[str, str]] | None = None,
    k: int = 5,
) -> list[list[str]]:
    """
    Find up to k alternative routes from from_node to to_node,
    optionally excluding certain edges (closed roads).

    Returns a list of paths (each path is a list of node IDs).
    """
    # Create a working copy to remove edges
    H = G.copy()
    if excluded_edges:
        for u, v in excluded_edges:
            if H.has_edge(u, v):
                H.remove_edge(u, v)
            if H.has_edge(v, u):
                H.remove_edge(v, u)

    routes = []
    try:
        # Find k shortest paths
        paths = list(nx.shortest_simple_paths(H, from_node, to_node, weight="weight"))
        for path in paths[:k]:
            routes.append(path)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        pass

    return routes


def get_roads_on_path(G: nx.DiGraph, path: list[str]) -> list[str]:
    """Get the road IDs along a path."""
    road_ids = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if G.has_edge(u, v):
            rid = G[u][v].get("road_id")
            if rid:
                road_ids.append(rid)
    return road_ids


def calculate_route_cost(G: nx.DiGraph, path: list[str]) -> float:
    """Calculate total travel time for a route."""
    total = 0.0
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        if G.has_edge(u, v):
            total += G[u][v].get("weight", 1.0)
    return total
