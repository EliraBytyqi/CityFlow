"""
Scenario management for CityFlow AI.

Provides functions for creating, retrieving, and comparing
traffic simulation scenarios.
"""

from sqlalchemy.orm import Session

from app.models import Simulation
from app.simulation.traffic_simulator import simulate_closure


def get_all_scenarios(db: Session) -> list[dict]:
    """Get all saved simulation scenarios."""
    sims = db.query(Simulation).order_by(Simulation.created_at.desc()).all()
    return [
        {
            "id": sim.id,
            "road_id": sim.road_id,
            "road_name": sim.road_name,
            "closure_percentage": sim.closure_percentage,
            "simulation_hour": sim.simulation_hour,
            "displaced_vehicles": sim.displaced_vehicles,
            "average_delay_percent": sim.average_delay_percent,
            "affected_roads_count": sim.affected_roads_count,
            "critical_roads_count": sim.critical_roads_count,
            "created_at": sim.created_at.isoformat() if sim.created_at else None,
        }
        for sim in sims
    ]


def compare_closures(
    db: Session,
    road_id: str,
    closure_percentages: list[int],
    simulation_hour: int = 8,
) -> dict:
    """
    Compare multiple closure percentages for the same road.
    Returns side-by-side results.
    """
    scenarios = []
    for pct in closure_percentages:
        result = simulate_closure(db, road_id, pct, simulation_hour)
        scenarios.append(result)

    road_name = scenarios[0]["closed_road_name"] if scenarios else ""

    return {
        "road_id": road_id,
        "road_name": road_name,
        "simulation_hour": simulation_hour,
        "scenarios": scenarios,
    }
