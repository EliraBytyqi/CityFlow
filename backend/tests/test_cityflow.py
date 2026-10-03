"""
Unit and Integration Tests for CityFlow AI.

Tests core components:
1. Traffic Ingestion (Adapter)
2. Traffic Aggregation
3. Road Network Graph Creation (NetworkX)
4. Congestion Model Calculation
5. Closure Simulation & Traffic Redistribution
6. Scenario Comparison
7. API Endpoints
8. End-to-End Flow
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models import Camera, Road, Intersection, TrafficMeasurement
from app.demo_data import seed_demo_data
from app.services.traffic_ingestion import TrafficModelAdapter
from app.schemas import DetectionIngestion, CountIngestion
from app.simulation.traffic_network import build_network
from app.simulation.congestion import calculate_utilization, classify_congestion, estimate_delay_percent
from app.simulation.traffic_simulator import simulate_closure
from app.simulation.scenario import compare_closures
from app.main import app

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_cityflow.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    seed_demo_data(session, force=True)
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ─── 1. Congestion Model Tests ────────────────────────────────────────
def test_congestion_model():
    assert calculate_utilization(500, 1000) == 0.5
    assert classify_congestion(0.40) == "low"
    assert classify_congestion(0.60) == "moderate"
    assert classify_congestion(0.80) == "high"
    assert classify_congestion(0.95) == "critical"
    assert estimate_delay_percent(0.40, 0.95) > 0.0


# ─── 2. Ingestion Adapter Tests ───────────────────────────────────────
def test_traffic_ingestion(db):
    # Test detection ingestion from external AI model
    detection = DetectionIngestion(
        camera_id="CAM_01",
        timestamp=datetime.now(timezone.utc),
        cars=82,
        trucks=7,
        buses=3,
        motorcycles=5,
        total=97,
    )
    measurement = TrafficModelAdapter.ingest_detection(db, detection)
    assert measurement.id is not None
    assert measurement.source == "observed"
    assert measurement.total == 97

    # Test count ingestion
    count = CountIngestion(
        camera_id="CAM_02",
        date="2026-10-03",
        hour=8,
        vehicle_count=1240,
    )
    m_count = TrafficModelAdapter.ingest_count(db, count)
    assert m_count.id is not None
    assert m_count.total == 1240


# ─── 3. Network & Simulation Tests ────────────────────────────────────
def test_road_network_creation(db):
    G = build_network(db)
    assert G.number_of_nodes() >= 10
    assert G.number_of_edges() >= 18


def test_closure_simulation_and_redistribution(db):
    # Simulate closing the Fushë Kosovë model link (road_01) 100%
    result = simulate_closure(db, road_id="road_01", closure_percentage=100, simulation_hour=8)

    assert result["closed_road"] == "road_01"
    assert result["closure_percentage"] == 100
    assert result["displaced_vehicles"] > 0
    assert result["affected_roads"] > 0
    assert len(result["roads"]) > 1
    assert result["explanation"] is not None

    # Closed road should have 0 after_flow
    closed_item = next(r for r in result["roads"] if r["road_id"] == "road_01")
    assert closed_item["after_flow"] == 0

    # Alternative roads should see an increase in flow
    increased_roads = [r for r in result["roads"] if r["road_id"] != "road_01" and r["change_percent"] > 0]
    assert len(increased_roads) > 0


def test_scenario_comparison(db):
    res = compare_closures(db, road_id="road_01", closure_percentages=[25, 50, 75, 100], simulation_hour=8)
    assert len(res["scenarios"]) == 4
    # Higher closure should displace more vehicles
    displaced_25 = res["scenarios"][0]["displaced_vehicles"]
    displaced_100 = res["scenarios"][3]["displaced_vehicles"]
    assert displaced_100 > displaced_25


# ─── 4. API Endpoint Tests ────────────────────────────────────────────
def test_api_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_api_roads(client):
    response = client.get("/api/roads")
    assert response.status_code == 200
    roads = response.json()
    assert len(roads) >= 18


def test_api_cameras(client):
    response = client.get("/api/cameras")
    assert response.status_code == 200
    cameras = response.json()
    assert len(cameras) >= 8


def test_api_traffic_summary(client):
    response = client.get("/api/traffic/summary")
    assert response.status_code == 200
    summary = response.json()
    assert summary["total_vehicles_today"] > 0


def test_api_simulation_endpoint(client):
    payload = {
        "road_id": "road_01",
        "closure_percentage": 100,
        "simulation_hour": 8,
    }
    response = client.post("/api/simulations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["closed_road"] == "road_01"
    assert data["displaced_vehicles"] > 0


# ─── 5. End-to-End Simulation Flow Test ──────────────────────────────
def test_e2e_flow(client):
    # Step 1: Query initial roads
    r_resp = client.get("/api/roads")
    roads = r_resp.json()
    target_link = next(r for r in roads if r["id"] == "road_01")
    initial_flow = target_link["current_flow"]
    assert initial_flow > 0

    # Step 2: Run simulation closure
    sim_resp = client.post("/api/simulations", json={
        "road_id": "road_01",
        "closure_percentage": 100,
        "simulation_hour": 8
    })
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()

    # Step 3: Verify displaced traffic and explanation
    assert sim_data["displaced_vehicles"] > 0
    assert len(sim_data["roads"]) > 1
    assert "Fushë Kosovë" in sim_data["explanation"]
