"""Pydantic schemas for CityFlow AI API."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─── Traffic Ingestion ────────────────────────────────────────────────
class DetectionIngestion(BaseModel):
    """Single detection event from the existing AI model."""
    camera_id: str
    timestamp: datetime
    cars: int = 0
    trucks: int = 0
    buses: int = 0
    motorcycles: int = 0
    total: int


class CountIngestion(BaseModel):
    """Aggregated count observation from the existing AI model."""
    camera_id: str
    date: str  # YYYY-MM-DD
    hour: int = Field(ge=0, le=23)
    vehicle_count: int


class IngestionResponse(BaseModel):
    status: str = "ok"
    message: str
    records_created: int = 1


# ─── Camera ──────────────────────────────────────────────────────────
class CameraOut(BaseModel):
    id: str
    name: str
    road_id: Optional[str] = None
    road_name: Optional[str] = None
    latitude: float
    longitude: float
    status: str
    latest_count: Optional[int] = None
    peak_hour: Optional[int] = None
    vehicles_per_hour: Optional[int] = None

    class Config:
        from_attributes = True


# ─── Road ────────────────────────────────────────────────────────────
class RoadOut(BaseModel):
    id: str
    name: str
    from_intersection: str
    to_intersection: str
    capacity: int
    current_flow: int
    length_km: float
    speed_limit: int
    lanes: int
    road_type: str
    utilization: float = 0.0
    status: str = "low"
    geometry: Optional[list] = None

    class Config:
        from_attributes = True


class RoadDetail(RoadOut):
    average_speed: float = 0.0
    peak_hour: Optional[int] = None
    camera_id: Optional[str] = None
    camera_name: Optional[str] = None
    hourly_data: Optional[list] = None


# ─── Traffic ─────────────────────────────────────────────────────────
class TrafficSummary(BaseModel):
    total_vehicles_today: int
    average_hourly: float
    peak_hour: int
    peak_count: int
    roads_monitored: int
    cameras_active: int
    data_source: str = "demo"  # "observed" | "demo"


class TrafficTimelinePoint(BaseModel):
    hour: int
    total: int
    cars: int = 0
    trucks: int = 0
    buses: int = 0
    motorcycles: int = 0


class TrafficTimeline(BaseModel):
    date: str
    data: list[TrafficTimelinePoint]
    data_source: str = "demo"


# ─── Simulation ──────────────────────────────────────────────────────
class SimulationRequest(BaseModel):
    road_id: str
    closure_percentage: int = Field(ge=0, le=100)
    simulation_hour: int = Field(default=8, ge=0, le=23)


class MultiRoadSimulationRequest(BaseModel):
    roads: list[dict]  # [{"road_id": "...", "closure_percentage": 100}]
    simulation_hour: int = Field(default=8, ge=0, le=23)


class AffectedRoad(BaseModel):
    road_id: str
    road_name: str
    before_flow: int
    after_flow: int
    change_percent: float
    capacity: int
    utilization: float
    status: str


class SimulationResponse(BaseModel):
    simulation_id: str
    closed_road: str
    closed_road_name: str
    closure_percentage: int
    simulation_hour: int
    displaced_vehicles: int
    average_delay_percent: float
    affected_roads: int
    critical_roads: int
    roads: list[AffectedRoad]
    explanation: str
    data_source: str = "simulated"


class CompareRequest(BaseModel):
    road_id: str
    closure_percentages: list[int] = [25, 50, 75, 100]
    simulation_hour: int = Field(default=8, ge=0, le=23)


class CompareResponse(BaseModel):
    road_id: str
    road_name: str
    simulation_hour: int
    scenarios: list[SimulationResponse]


# ─── Scenario ────────────────────────────────────────────────────────
class ScenarioOut(BaseModel):
    id: str
    road_id: str
    road_name: str
    closure_percentage: int
    simulation_hour: int
    displaced_vehicles: int
    average_delay_percent: float
    affected_roads_count: int
    critical_roads_count: int
    created_at: Optional[datetime] = None


# ─── Health ──────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    database: str = "connected"
    demo_mode: bool = True
