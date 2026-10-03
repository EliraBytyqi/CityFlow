"""SQLAlchemy models for CityFlow AI."""

from sqlalchemy import (
    Column, Integer, Float, String, DateTime, ForeignKey, Text, Boolean, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    road_id = Column(String, ForeignKey("roads.id"), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(String, default="online")  # online / offline
    stream_url = Column(String, nullable=True)
    installed_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    measurements = relationship("TrafficMeasurement", back_populates="camera")
    road = relationship("Road", back_populates="cameras")


class Road(Base):
    __tablename__ = "roads"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    from_intersection = Column(String, ForeignKey("intersections.id"), nullable=False)
    to_intersection = Column(String, ForeignKey("intersections.id"), nullable=False)
    capacity = Column(Integer, nullable=False)  # vehicles/day
    current_flow = Column(Integer, default=0)   # vehicles/day (latest)
    length_km = Column(Float, nullable=False)
    speed_limit = Column(Integer, default=50)   # km/h
    lanes = Column(Integer, default=2)
    road_type = Column(String, default="secondary")  # primary / secondary / tertiary

    # Geometry for map rendering (list of [lng, lat] coordinates)
    geometry = Column(JSON, nullable=True)

    cameras = relationship("Camera", back_populates="road")
    from_node = relationship("Intersection", foreign_keys=[from_intersection])
    to_node = relationship("Intersection", foreign_keys=[to_intersection])


class Intersection(Base):
    __tablename__ = "intersections"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    intersection_type = Column(String, default="signalized")  # signalized / roundabout / uncontrolled


class TrafficMeasurement(Base):
    __tablename__ = "traffic_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String, ForeignKey("cameras.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    hour = Column(Integer, nullable=False)
    cars = Column(Integer, default=0)
    trucks = Column(Integer, default=0)
    buses = Column(Integer, default=0)
    motorcycles = Column(Integer, default=0)
    total = Column(Integer, nullable=False)
    source = Column(String, default="observed")  # observed / estimated / demo

    camera = relationship("Camera", back_populates="measurements")


class Simulation(Base):
    __tablename__ = "simulations"

    id = Column(String, primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    road_id = Column(String, nullable=False)
    road_name = Column(String, nullable=False)
    closure_percentage = Column(Integer, nullable=False)
    simulation_hour = Column(Integer, default=8)  # hour of day for the simulation
    status = Column(String, default="completed")
    displaced_vehicles = Column(Integer, default=0)
    average_delay_percent = Column(Float, default=0.0)
    affected_roads_count = Column(Integer, default=0)
    critical_roads_count = Column(Integer, default=0)
    explanation = Column(Text, nullable=True)
    results_json = Column(JSON, nullable=True)  # full results


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    simulation_id = Column(String, ForeignKey("simulations.id"), nullable=False)
    road_id = Column(String, nullable=False)
    road_name = Column(String, nullable=False)
    before_flow = Column(Integer, nullable=False)
    after_flow = Column(Integer, nullable=False)
    change_percent = Column(Float, nullable=False)
    capacity = Column(Integer, nullable=False)
    utilization = Column(Float, nullable=False)
    status = Column(String, nullable=False)  # low / moderate / high / critical

    simulation = relationship("Simulation", backref="results")
