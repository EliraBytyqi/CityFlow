"""
Traffic Ingestion Service for CityFlow AI.

Provides a modular adapter layer between the existing AI vehicle-detection
model and the CityFlow platform. The TrafficModelAdapter class handles
ingesting detection events and aggregated counts, storing them in the
database using the same schema as demo data.

This module does NOT implement or assume anything about the external
AI model's internals. It only defines the interface for receiving
its output.

To replace the adapter later, implement the same interface:
  - ingest_detection(db, detection)
  - ingest_count(db, count)
  - get_measurements(db, camera_id, date, start_hour, end_hour)
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models import TrafficMeasurement, Camera, Road
from app.schemas import DetectionIngestion, CountIngestion


class TrafficModelAdapter:
    """
    Adapter for ingesting vehicle detection data from the existing
    trained AI model into the CityFlow platform.

    This class is the ONLY integration point between the external
    model and CityFlow. All data from the model flows through here.
    """

    @staticmethod
    def ingest_detection(db: Session, detection: DetectionIngestion) -> TrafficMeasurement:
        """
        Ingest a single detection event from the AI model.

        Expected format:
        {
            "camera_id": "CAM_01",
            "timestamp": "2026-10-03T08:15:00",
            "cars": 82,
            "trucks": 7,
            "buses": 3,
            "motorcycles": 5,
            "total": 97
        }
        """
        # Validate camera exists
        camera = db.query(Camera).filter(Camera.id == detection.camera_id).first()
        if not camera:
            raise ValueError(f"Unknown camera: {detection.camera_id}")

        measurement = TrafficMeasurement(
            camera_id=detection.camera_id,
            timestamp=detection.timestamp,
            hour=detection.timestamp.hour,
            cars=detection.cars,
            trucks=detection.trucks,
            buses=detection.buses,
            motorcycles=detection.motorcycles,
            total=detection.total,
            source="observed",  # Data from the real AI model
        )
        db.add(measurement)
        db.commit()
        db.refresh(measurement)

        # Update road's current flow if camera is linked to a road
        if camera.road_id:
            TrafficModelAdapter._update_road_flow(db, camera.road_id)

        return measurement

    @staticmethod
    def ingest_count(db: Session, count: CountIngestion) -> TrafficMeasurement:
        """
        Ingest an aggregated count observation from the AI model.

        Expected format:
        {
            "camera_id": "CAM_01",
            "date": "2026-10-03",
            "hour": 8,
            "vehicle_count": 1240
        }
        """
        camera = db.query(Camera).filter(Camera.id == count.camera_id).first()
        if not camera:
            raise ValueError(f"Unknown camera: {count.camera_id}")

        # Parse date
        date = datetime.strptime(count.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        ts = date.replace(hour=count.hour)

        # Estimate vehicle composition (since aggregated count doesn't have it)
        total = count.vehicle_count
        cars = int(total * 0.78)
        trucks = int(total * 0.08)
        buses = int(total * 0.04)
        motorcycles = total - cars - trucks - buses

        measurement = TrafficMeasurement(
            camera_id=count.camera_id,
            timestamp=ts,
            hour=count.hour,
            cars=cars,
            trucks=trucks,
            buses=buses,
            motorcycles=motorcycles,
            total=total,
            source="observed",
        )
        db.add(measurement)
        db.commit()
        db.refresh(measurement)

        if camera.road_id:
            TrafficModelAdapter._update_road_flow(db, camera.road_id)

        return measurement

    @staticmethod
    def get_measurements(
        db: Session,
        camera_id: str | None = None,
        start_hour: int = 0,
        end_hour: int = 23,
    ) -> list[TrafficMeasurement]:
        """
        Retrieve stored measurements, optionally filtered by camera and hour range.
        """
        query = db.query(TrafficMeasurement)
        if camera_id:
            query = query.filter(TrafficMeasurement.camera_id == camera_id)
        query = query.filter(
            and_(
                TrafficMeasurement.hour >= start_hour,
                TrafficMeasurement.hour <= end_hour,
            )
        )
        return query.order_by(TrafficMeasurement.hour).all()

    @staticmethod
    def _update_road_flow(db: Session, road_id: str):
        """
        Update a road's current_flow based on latest camera measurements.
        Sums total daily traffic from all cameras on this road.
        """
        cameras = db.query(Camera).filter(Camera.road_id == road_id).all()
        total_daily = 0
        for cam in cameras:
            measurements = (
                db.query(TrafficMeasurement)
                .filter(TrafficMeasurement.camera_id == cam.id)
                .all()
            )
            total_daily += sum(m.total for m in measurements)

        road = db.query(Road).filter(Road.id == road_id).first()
        if road:
            road.current_flow = total_daily
            db.commit()
