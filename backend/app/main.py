"""
CityFlow AI — FastAPI Backend

"See the impact before you change the street."

A smart-city traffic simulation platform that works with
an existing AI vehicle-detection model.
"""

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db, init_db
from app.models import Camera, Road, Intersection, TrafficMeasurement, Simulation, SimulationResult
from app.schemas import (
    HealthResponse,
    CameraOut,
    RoadOut,
    RoadDetail,
    TrafficSummary,
    TrafficTimeline,
    TrafficTimelinePoint,
    DetectionIngestion,
    CountIngestion,
    IngestionResponse,
    SimulationRequest,
    SimulationResponse,
    AffectedRoad,
    CompareRequest,
    CompareResponse,
    MultiRoadSimulationRequest,
)
from app.demo_data import seed_demo_data, _traffic_multiplier
from app.services.traffic_ingestion import TrafficModelAdapter
from app.simulation.traffic_simulator import simulate_closure, simulate_multi_closure
from app.simulation.scenario import get_all_scenarios, compare_closures
from app.simulation.congestion import calculate_utilization, classify_congestion, estimate_speed


app = FastAPI(
    title="CityFlow AI",
    description="Smart-city traffic simulation platform",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Initialize database and seed demo data on first run."""
    init_db()
    db = next(get_db())
    try:
        seed_demo_data(db)
    finally:
        db.close()


# ─── Health ──────────────────────────────────────────────────────────
@app.get("/api/health", response_model=HealthResponse)
def health():
    return HealthResponse()


# ─── Roads ───────────────────────────────────────────────────────────
@app.get("/api/roads")
def get_roads(db: Session = Depends(get_db)):
    """Get all roads with current utilization."""
    roads = db.query(Road).all()
    result = []
    for r in roads:
        util = calculate_utilization(r.current_flow, r.capacity)
        result.append({
            "id": r.id,
            "name": r.name,
            "from_intersection": r.from_intersection,
            "to_intersection": r.to_intersection,
            "capacity": r.capacity,
            "current_flow": r.current_flow,
            "length_km": r.length_km,
            "speed_limit": r.speed_limit,
            "lanes": r.lanes,
            "road_type": r.road_type,
            "utilization": round(util, 2),
            "status": classify_congestion(util),
            "geometry": r.geometry,
        })
    return result


@app.get("/api/roads/{road_id}")
def get_road(road_id: str, db: Session = Depends(get_db)):
    """Get detailed road info including hourly data."""
    road = db.query(Road).filter(Road.id == road_id).first()
    if not road:
        raise HTTPException(status_code=404, detail="Road not found")

    util = calculate_utilization(road.current_flow, road.capacity)
    avg_speed = estimate_speed(road.speed_limit, util)

    # Find associated camera
    camera = db.query(Camera).filter(Camera.road_id == road_id).first()

    # Get hourly data
    hourly_data = []
    if camera:
        measurements = (
            db.query(TrafficMeasurement)
            .filter(TrafficMeasurement.camera_id == camera.id)
            .order_by(TrafficMeasurement.hour)
            .all()
        )
        for m in measurements:
            hourly_data.append({
                "hour": m.hour,
                "total": m.total,
                "cars": m.cars,
                "trucks": m.trucks,
                "buses": m.buses,
                "motorcycles": m.motorcycles,
                "source": m.source,
            })
        peak = max(measurements, key=lambda m: m.total) if measurements else None
    else:
        peak = None

    return {
        "id": road.id,
        "name": road.name,
        "from_intersection": road.from_intersection,
        "to_intersection": road.to_intersection,
        "capacity": road.capacity,
        "current_flow": road.current_flow,
        "length_km": road.length_km,
        "speed_limit": road.speed_limit,
        "lanes": road.lanes,
        "road_type": road.road_type,
        "utilization": round(util, 2),
        "status": classify_congestion(util),
        "average_speed": round(avg_speed, 1),
        "peak_hour": peak.hour if peak else None,
        "camera_id": camera.id if camera else None,
        "camera_name": camera.name if camera else None,
        "hourly_data": hourly_data,
        "geometry": road.geometry,
        "data_source": "observed" if camera else "estimated",
    }


# ─── Intersections ───────────────────────────────────────────────────
@app.get("/api/intersections")
def get_intersections(db: Session = Depends(get_db)):
    """Get all intersections."""
    ints = db.query(Intersection).all()
    return [
        {
            "id": i.id,
            "name": i.name,
            "latitude": i.latitude,
            "longitude": i.longitude,
            "type": i.intersection_type,
        }
        for i in ints
    ]


# ─── Cameras ─────────────────────────────────────────────────────────
@app.get("/api/cameras")
def get_cameras(db: Session = Depends(get_db)):
    """Get all cameras with latest stats."""
    cameras = db.query(Camera).all()
    result = []
    for cam in cameras:
        # Get latest measurement stats
        measurements = (
            db.query(TrafficMeasurement)
            .filter(TrafficMeasurement.camera_id == cam.id)
            .all()
        )
        total_count = sum(m.total for m in measurements)
        peak = max(measurements, key=lambda m: m.total) if measurements else None

        # Get road name
        road_name = None
        if cam.road_id:
            road = db.query(Road).filter(Road.id == cam.road_id).first()
            road_name = road.name if road else None

        result.append({
            "id": cam.id,
            "name": cam.name,
            "road_id": cam.road_id,
            "road_name": road_name,
            "latitude": cam.latitude,
            "longitude": cam.longitude,
            "status": cam.status,
            "latest_count": total_count,
            "peak_hour": peak.hour if peak else None,
            "vehicles_per_hour": peak.total if peak else None,
        })
    return result


@app.get("/api/cameras/{camera_id}")
def get_camera_detail(camera_id: str, db: Session = Depends(get_db)):
    """Get detailed camera info with 24h data."""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    measurements = (
        db.query(TrafficMeasurement)
        .filter(TrafficMeasurement.camera_id == camera_id)
        .order_by(TrafficMeasurement.hour)
        .all()
    )

    road = db.query(Road).filter(Road.id == camera.road_id).first() if camera.road_id else None

    hourly_data = [
        {
            "hour": m.hour,
            "total": m.total,
            "cars": m.cars,
            "trucks": m.trucks,
            "buses": m.buses,
            "motorcycles": m.motorcycles,
            "source": m.source,
        }
        for m in measurements
    ]

    peak = max(measurements, key=lambda m: m.total) if measurements else None

    return {
        "id": camera.id,
        "name": camera.name,
        "road_id": camera.road_id,
        "road_name": road.name if road else None,
        "latitude": camera.latitude,
        "longitude": camera.longitude,
        "status": camera.status,
        "total_daily": sum(m.total for m in measurements),
        "peak_hour": peak.hour if peak else None,
        "peak_count": peak.total if peak else None,
        "hourly_data": hourly_data,
        "data_source": measurements[0].source if measurements else "demo",
    }


# ─── Traffic ─────────────────────────────────────────────────────────
@app.get("/api/traffic/summary")
def traffic_summary(db: Session = Depends(get_db)):
    """Get overall traffic summary."""
    measurements = db.query(TrafficMeasurement).all()

    # Aggregate by hour across all cameras
    hourly_totals = {}
    for m in measurements:
        hourly_totals[m.hour] = hourly_totals.get(m.hour, 0) + m.total

    total_today = sum(hourly_totals.values())
    peak_hour = max(hourly_totals, key=hourly_totals.get) if hourly_totals else 0
    peak_count = hourly_totals.get(peak_hour, 0)
    avg_hourly = total_today / 24 if total_today > 0 else 0

    roads_count = db.query(Road).count()
    cameras_count = db.query(Camera).filter(Camera.status == "online").count()

    # Check if we have observed data
    observed = db.query(TrafficMeasurement).filter(TrafficMeasurement.source == "observed").count()
    data_source = "observed" if observed > 0 else "demo"

    return {
        "total_vehicles_today": total_today,
        "average_hourly": round(avg_hourly),
        "peak_hour": peak_hour,
        "peak_count": peak_count,
        "roads_monitored": roads_count,
        "cameras_active": cameras_count,
        "data_source": data_source,
    }


@app.get("/api/traffic/timeline")
def traffic_timeline(db: Session = Depends(get_db)):
    """Get 24-hour traffic timeline with vehicle composition."""
    measurements = db.query(TrafficMeasurement).all()

    hourly = {}
    for m in measurements:
        if m.hour not in hourly:
            hourly[m.hour] = {"total": 0, "cars": 0, "trucks": 0, "buses": 0, "motorcycles": 0}
        hourly[m.hour]["total"] += m.total
        hourly[m.hour]["cars"] += m.cars
        hourly[m.hour]["trucks"] += m.trucks
        hourly[m.hour]["buses"] += m.buses
        hourly[m.hour]["motorcycles"] += m.motorcycles

    data = []
    for h in range(24):
        d = hourly.get(h, {"total": 0, "cars": 0, "trucks": 0, "buses": 0, "motorcycles": 0})
        data.append({
            "hour": h,
            "total": d["total"],
            "cars": d["cars"],
            "trucks": d["trucks"],
            "buses": d["buses"],
            "motorcycles": d["motorcycles"],
        })

    observed = db.query(TrafficMeasurement).filter(TrafficMeasurement.source == "observed").count()

    return {
        "date": "2026-10-03",
        "data": data,
        "data_source": "observed" if observed > 0 else "demo",
    }


@app.get("/api/traffic/road/{road_id}")
def traffic_by_road(road_id: str, db: Session = Depends(get_db)):
    """Get traffic data for a specific road."""
    road = db.query(Road).filter(Road.id == road_id).first()
    if not road:
        raise HTTPException(status_code=404, detail="Road not found")

    camera = db.query(Camera).filter(Camera.road_id == road_id).first()
    hourly_data = []

    if camera:
        measurements = (
            db.query(TrafficMeasurement)
            .filter(TrafficMeasurement.camera_id == camera.id)
            .order_by(TrafficMeasurement.hour)
            .all()
        )
        for m in measurements:
            hourly_data.append({
                "hour": m.hour,
                "total": m.total,
                "cars": m.cars,
                "trucks": m.trucks,
                "buses": m.buses,
                "motorcycles": m.motorcycles,
            })

    return {
        "road_id": road.id,
        "road_name": road.name,
        "capacity": road.capacity,
        "current_flow": road.current_flow,
        "hourly_data": hourly_data,
        "data_source": "observed" if camera else "estimated",
    }


# ─── Traffic Ingestion ───────────────────────────────────────────────
@app.post("/api/traffic/ingest")
def ingest_traffic(
    detection: DetectionIngestion | None = None,
    count: CountIngestion | None = None,
    db: Session = Depends(get_db),
):
    """
    Ingest traffic data from the existing AI vehicle-detection model.
    Accepts either a detection event or an aggregated count.
    """
    if detection:
        try:
            TrafficModelAdapter.ingest_detection(db, detection)
            return {"status": "ok", "message": "Detection ingested", "records_created": 1}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif count:
        try:
            TrafficModelAdapter.ingest_count(db, count)
            return {"status": "ok", "message": "Count ingested", "records_created": 1}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Provide detection or count data")


@app.post("/api/traffic/ingest/detection")
def ingest_detection(detection: DetectionIngestion, db: Session = Depends(get_db)):
    """Ingest a detection event from the existing AI model."""
    try:
        TrafficModelAdapter.ingest_detection(db, detection)
        return {"status": "ok", "message": "Detection ingested", "records_created": 1}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/traffic/ingest/count")
def ingest_count(count: CountIngestion, db: Session = Depends(get_db)):
    """Ingest an aggregated count from the existing AI model."""
    try:
        TrafficModelAdapter.ingest_count(db, count)
        return {"status": "ok", "message": "Count ingested", "records_created": 1}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Simulations ─────────────────────────────────────────────────────
@app.post("/api/simulations")
def run_simulation(req: SimulationRequest, db: Session = Depends(get_db)):
    """Run a traffic closure simulation."""
    try:
        result = simulate_closure(db, req.road_id, req.closure_percentage, req.simulation_hour)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/simulations/multi")
def run_multi_simulation(req: MultiRoadSimulationRequest, db: Session = Depends(get_db)):
    """Run a multi-road closure simulation."""
    try:
        result = simulate_multi_closure(db, req.roads, req.simulation_hour)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/simulations/{simulation_id}")
def get_simulation(simulation_id: str, db: Session = Depends(get_db)):
    """Get a saved simulation result."""
    sim = db.query(Simulation).filter(Simulation.id == simulation_id).first()
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    results = db.query(SimulationResult).filter(
        SimulationResult.simulation_id == simulation_id
    ).all()

    return {
        "simulation_id": sim.id,
        "closed_road": sim.road_id,
        "closed_road_name": sim.road_name,
        "closure_percentage": sim.closure_percentage,
        "simulation_hour": sim.simulation_hour,
        "displaced_vehicles": sim.displaced_vehicles,
        "average_delay_percent": sim.average_delay_percent,
        "affected_roads": sim.affected_roads_count,
        "critical_roads": sim.critical_roads_count,
        "explanation": sim.explanation,
        "roads": [
            {
                "road_id": r.road_id,
                "road_name": r.road_name,
                "before_flow": r.before_flow,
                "after_flow": r.after_flow,
                "change_percent": r.change_percent,
                "capacity": r.capacity,
                "utilization": r.utilization,
                "status": r.status,
            }
            for r in results
        ],
        "data_source": "simulated",
    }


@app.post("/api/simulations/compare")
def compare_simulations(req: CompareRequest, db: Session = Depends(get_db)):
    """Compare multiple closure percentages for the same road."""
    try:
        result = compare_closures(
            db, req.road_id, req.closure_percentages, req.simulation_hour
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Scenarios ───────────────────────────────────────────────────────
@app.get("/api/scenarios")
def list_scenarios(db: Session = Depends(get_db)):
    """Get all saved simulation scenarios."""
    return get_all_scenarios(db)
