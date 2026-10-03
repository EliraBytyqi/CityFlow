"""
Deterministic demo data generator for CityFlow AI.

Creates a realistic small-city road network with 8 cameras,
18 roads, 10 intersections, and 24 hours of synthetic traffic
measurements that follow realistic daily patterns.

All demo data follows the same schema as real AI model output.
"""

import math
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models import Camera, Road, Intersection, TrafficMeasurement

# Fix the seed for deterministic demo data
SEED = 42


def _traffic_multiplier(hour: int) -> float:
    """
    Realistic traffic pattern multiplier by hour.
    00-05: low | 07-09: morning peak | 10-15: moderate
    16-18: evening peak | 20-24: declining
    """
    pattern = {
        0: 0.08, 1: 0.05, 2: 0.04, 3: 0.03, 4: 0.04, 5: 0.06,
        6: 0.15, 7: 0.55, 8: 0.92, 9: 0.78,
        10: 0.52, 11: 0.55, 12: 0.60, 13: 0.58, 14: 0.55, 15: 0.62,
        16: 0.80, 17: 0.95, 18: 0.75,
        19: 0.45, 20: 0.30, 21: 0.22, 22: 0.15, 23: 0.10,
    }
    return pattern.get(hour, 0.3)


def _vehicle_composition(total: int, rng: random.Random) -> dict:
    """Realistic split of vehicles into types."""
    car_pct = 0.78 + rng.uniform(-0.03, 0.03)
    truck_pct = 0.08 + rng.uniform(-0.02, 0.02)
    bus_pct = 0.04 + rng.uniform(-0.01, 0.01)
    moto_pct = 1.0 - car_pct - truck_pct - bus_pct

    cars = int(total * car_pct)
    trucks = int(total * truck_pct)
    buses = int(total * bus_pct)
    motorcycles = max(0, total - cars - trucks - buses)

    return {"cars": cars, "trucks": trucks, "buses": buses, "motorcycles": motorcycles}


# ─── Network Definition ─────────────────────────────────────────────
# A small Dutch-style city center with realistic street names
# Coordinates centered around a fictional city (based on Delft-like layout)
# Using real-ish coordinates near 52.01°N, 4.36°E

INTERSECTIONS = [
    {"id": "int_01", "name": "Marktplein",        "lat": 52.0120, "lng": 4.3580, "type": "signalized"},
    {"id": "int_02", "name": "Stationsplein",     "lat": 52.0155, "lng": 4.3580, "type": "signalized"},
    {"id": "int_03", "name": "Noordpoort",        "lat": 52.0175, "lng": 4.3620, "type": "roundabout"},
    {"id": "int_04", "name": "Oost Kruising",     "lat": 52.0130, "lng": 4.3660, "type": "signalized"},
    {"id": "int_05", "name": "Zuidplein",         "lat": 52.0085, "lng": 4.3600, "type": "signalized"},
    {"id": "int_06", "name": "West Kruising",     "lat": 52.0130, "lng": 4.3500, "type": "signalized"},
    {"id": "int_07", "name": "Haven Kruising",    "lat": 52.0100, "lng": 4.3520, "type": "roundabout"},
    {"id": "int_08", "name": "Park Kruising",     "lat": 52.0160, "lng": 4.3500, "type": "uncontrolled"},
    {"id": "int_09", "name": "Industrieplein",    "lat": 52.0180, "lng": 4.3540, "type": "signalized"},
    {"id": "int_10", "name": "Brug Kruising",     "lat": 52.0095, "lng": 4.3660, "type": "signalized"},
]

ROADS = [
    {"id": "road_01", "name": "Weststraat",       "from": "int_06", "to": "int_01", "cap": 3100, "flow": 2430, "len": 0.8, "speed": 40, "lanes": 2, "type": "primary"},
    {"id": "road_02", "name": "Noordweg",          "from": "int_02", "to": "int_03", "cap": 2200, "flow": 700,  "len": 0.5, "speed": 50, "lanes": 2, "type": "secondary"},
    {"id": "road_03", "name": "Kerkstraat",        "from": "int_01", "to": "int_04", "cap": 1800, "flow": 620,  "len": 0.6, "speed": 30, "lanes": 1, "type": "secondary"},
    {"id": "road_04", "name": "Marktstraat",       "from": "int_01", "to": "int_05", "cap": 2500, "flow": 450,  "len": 0.4, "speed": 30, "lanes": 2, "type": "primary"},
    {"id": "road_05", "name": "Stationsweg",       "from": "int_01", "to": "int_02", "cap": 3500, "flow": 2800, "len": 1.0, "speed": 50, "lanes": 2, "type": "primary"},
    {"id": "road_06", "name": "Havenstraat",       "from": "int_07", "to": "int_05", "cap": 1600, "flow": 520,  "len": 0.7, "speed": 30, "lanes": 1, "type": "secondary"},
    {"id": "road_07", "name": "Parkweg",           "from": "int_08", "to": "int_06", "cap": 1900, "flow": 380,  "len": 0.9, "speed": 40, "lanes": 2, "type": "secondary"},
    {"id": "road_08", "name": "Industrieweg",      "from": "int_09", "to": "int_03", "cap": 2800, "flow": 1950, "len": 1.2, "speed": 60, "lanes": 2, "type": "primary"},
    {"id": "road_09", "name": "Brugstraat",        "from": "int_05", "to": "int_10", "cap": 1400, "flow": 410,  "len": 0.3, "speed": 30, "lanes": 1, "type": "tertiary"},
    {"id": "road_10", "name": "Oosterweg",         "from": "int_04", "to": "int_10", "cap": 2000, "flow": 780,  "len": 0.6, "speed": 40, "lanes": 2, "type": "secondary"},
    {"id": "road_11", "name": "Ringweg Noord",     "from": "int_09", "to": "int_02", "cap": 4000, "flow": 3100, "len": 1.5, "speed": 70, "lanes": 2, "type": "primary"},
    {"id": "road_12", "name": "Ringweg West",      "from": "int_08", "to": "int_09", "cap": 3800, "flow": 2600, "len": 1.3, "speed": 70, "lanes": 2, "type": "primary"},
    {"id": "road_13", "name": "Kanaalweg",         "from": "int_07", "to": "int_06", "cap": 1500, "flow": 480,  "len": 0.5, "speed": 30, "lanes": 1, "type": "tertiary"},
    {"id": "road_14", "name": "Molenstraat",       "from": "int_02", "to": "int_04", "cap": 1700, "flow": 590,  "len": 0.8, "speed": 30, "lanes": 1, "type": "secondary"},
    {"id": "road_15", "name": "Vijverweg",         "from": "int_06", "to": "int_07", "cap": 1200, "flow": 310,  "len": 0.4, "speed": 30, "lanes": 1, "type": "tertiary"},
    {"id": "road_16", "name": "Schoolstraat",      "from": "int_03", "to": "int_04", "cap": 1600, "flow": 540,  "len": 0.5, "speed": 30, "lanes": 1, "type": "secondary"},
    {"id": "road_17", "name": "Ringweg Zuid",      "from": "int_07", "to": "int_10", "cap": 3200, "flow": 1850, "len": 1.4, "speed": 60, "lanes": 2, "type": "primary"},
    {"id": "road_18", "name": "Centrumring",       "from": "int_05", "to": "int_01", "cap": 2000, "flow": 920,  "len": 0.5, "speed": 30, "lanes": 2, "type": "secondary"},
]

# Generate geometry (polylines) for each road based on endpoint coordinates
def _generate_geometry():
    """Build a lookup from intersection id to its coords."""
    coords = {i["id"]: (i["lng"], i["lat"]) for i in INTERSECTIONS}
    geometries = {}
    for road in ROADS:
        start = coords[road["from"]]
        end = coords[road["to"]]
        # Add a slight curve for visual interest
        mid_lng = (start[0] + end[0]) / 2 + 0.0005 * (hash(road["id"]) % 3 - 1)
        mid_lat = (start[1] + end[1]) / 2 + 0.0003 * (hash(road["id"]) % 3 - 1)
        geometries[road["id"]] = [
            list(start),
            [mid_lng, mid_lat],
            list(end)
        ]
    return geometries


CAMERAS = [
    {"id": "CAM_01", "name": "Fushë Kosovë", "road": "road_01", "lat": 42.6397, "lng": 21.0960, "stream_url": "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/5zv-jaz-xqj-y20/tracks-v1a1/mono.ts.m3u8"},
    {"id": "CAM_02", "name": "Ulpianë", "road": "road_02", "lat": 42.6500, "lng": 21.1600, "stream_url": "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/mc7-cgv-ra3-a61/tracks-v1a1/mono.ts.m3u8"},
    {"id": "CAM_03", "name": "Bregu i Diellit", "road": "road_05", "lat": 42.6480, "lng": 21.1660, "stream_url": "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/jrl-15u-0vp-6r8/tracks-a1/mono.ts.m3u8"},
    {"id": "CAM_04", "name": "Pejton", "road": "road_03", "lat": 42.6570, "lng": 21.1530, "stream_url": "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/mc7-cgv-ra3-a61/tracks-a1/mono.ts.m3u8"},
    {"id": "CAM_05", "name": "Magjistralja Vushtrri–Mitrovicë", "road": "road_08", "lat": 42.8850, "lng": 20.8660, "stream_url": "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/zc6-dfj-mel-af4/tracks-a1/mono.ts.m3u8"},
    {"id": "CAM_06", "name": "Ortakoll: Wesley Clark, Prizren", "road": "road_11", "lat": 42.2140, "lng": 20.7390, "stream_url": "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/yfv-44d-9m7-6sy/tracks-a1/mono.ts.m3u8"},
    {"id": "CAM_07", "name": "Camera Ringweg Zuid", "road": "road_17", "lat": 52.0098, "lng": 4.3590},
    {"id": "CAM_08", "name": "Camera Marktstraat", "road": "road_04", "lat": 52.0103, "lng": 4.3590},
]


def seed_demo_data(db: Session, force: bool = False):
    """Seed the database with deterministic demo data."""
    # Check if already seeded
    existing = db.query(Camera).count()
    if existing > 0 and not force:
        return False

    if force:
        db.query(TrafficMeasurement).delete()
        db.query(Camera).delete()
        db.query(Road).delete()
        db.query(Intersection).delete()
        db.commit()

    rng = random.Random(SEED)
    geometries = _generate_geometry()

    # ── Create Intersections ──
    for i in INTERSECTIONS:
        db.add(Intersection(
            id=i["id"],
            name=i["name"],
            latitude=i["lat"],
            longitude=i["lng"],
            intersection_type=i["type"],
        ))

    # ── Create Roads ──
    for r in ROADS:
        db.add(Road(
            id=r["id"],
            name=r["name"],
            from_intersection=r["from"],
            to_intersection=r["to"],
            capacity=r["cap"],
            current_flow=r["flow"],
            length_km=r["len"],
            speed_limit=r["speed"],
            lanes=r["lanes"],
            road_type=r["type"],
            geometry=geometries.get(r["id"]),
        ))

    # ── Create Cameras ──
    for c in CAMERAS:
        db.add(Camera(
            id=c["id"],
            name=c["name"],
            road_id=c["road"],
            latitude=c["lat"],
            longitude=c["lng"],
            status="online",
        ))

    db.commit()

    # ── Create 24-hour Traffic Measurements ──
    # We generate one measurement per camera per hour
    demo_date = datetime(2026, 10, 3, tzinfo=timezone.utc)

    # Map cameras to their road's daily flow for scaling
    cam_road_flow = {}
    for c in CAMERAS:
        for r in ROADS:
            if r["id"] == c["road"]:
                cam_road_flow[c["id"]] = r["flow"]
                break

    for cam in CAMERAS:
        daily_flow = cam_road_flow.get(cam["id"], 1000)

        for hour in range(24):
            multiplier = _traffic_multiplier(hour)
            # hourly count is scaled from daily total
            base_hourly = daily_flow * multiplier / sum(_traffic_multiplier(h) for h in range(24))
            # Add slight random variation (deterministic)
            noise = 1.0 + rng.uniform(-0.05, 0.05)
            hourly_total = max(1, int(base_hourly * noise))

            composition = _vehicle_composition(hourly_total, rng)

            ts = demo_date.replace(hour=hour, minute=rng.randint(0, 59))
            db.add(TrafficMeasurement(
                camera_id=cam["id"],
                timestamp=ts,
                hour=hour,
                cars=composition["cars"],
                trucks=composition["trucks"],
                buses=composition["buses"],
                motorcycles=composition["motorcycles"],
                total=hourly_total,
                source="demo",
            ))

    db.commit()
    return True


def get_hourly_flow_for_road(db: Session, road_id: str) -> dict[int, int]:
    """
    Get traffic flow by hour for a specific road.
    Returns {hour: vehicle_count}.
    """
    # Find camera for this road
    camera = db.query(Camera).filter(Camera.road_id == road_id).first()
    if not camera:
        # No camera: estimate from road's current_flow using pattern
        road = db.query(Road).filter(Road.id == road_id).first()
        if not road:
            return {h: 0 for h in range(24)}
        daily = road.current_flow
        total_mult = sum(_traffic_multiplier(h) for h in range(24))
        return {h: int(daily * _traffic_multiplier(h) / total_mult) for h in range(24)}

    # Get measurements
    measurements = (
        db.query(TrafficMeasurement)
        .filter(TrafficMeasurement.camera_id == camera.id)
        .all()
    )
    hourly = {}
    for m in measurements:
        hourly[m.hour] = m.total
    # Fill gaps
    for h in range(24):
        if h not in hourly:
            hourly[h] = 0
    return hourly
