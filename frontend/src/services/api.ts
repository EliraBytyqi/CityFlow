/**
 * CityFlow AI — API Service Layer
 *
 * Centralized API client for all backend communication.
 * All requests go through this module.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─── Types ──────────────────────────────────────────────────────────

export interface Road {
  id: string;
  name: string;
  from_intersection: string;
  to_intersection: string;
  capacity: number;
  current_flow: number;
  length_km: number;
  speed_limit: number;
  lanes: number;
  road_type: string;
  utilization: number;
  status: string;
  geometry: number[][] | null;
}

export interface RoadDetail extends Road {
  average_speed: number;
  peak_hour: number | null;
  camera_id: string | null;
  camera_name: string | null;
  hourly_data: HourlyDataPoint[];
  data_source: string;
}

export interface Intersection {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  type: string;
}

export interface Camera {
  id: string;
  name: string;
  road_id: string | null;
  road_name: string | null;
  latitude: number;
  longitude: number;
  status: string;
  latest_count: number | null;
  peak_hour: number | null;
  vehicles_per_hour: number | null;
  stream_url: string | null;
}

export interface CameraDetail extends Camera {
  total_daily: number;
  peak_count: number | null;
  hourly_data: HourlyDataPoint[];
  data_source: string;
}

export interface CameraInference {
  camera_id: string;
  status: 'stopped' | 'connecting' | 'live' | 'error';
  error?: string | null;
  counts: { cars?: number; trucks?: number; buses?: number; motorcycles?: number };
  total: number;
  updated_at?: string | null;
}

export interface HourlyDataPoint {
  hour: number;
  total: number;
  cars: number;
  trucks: number;
  buses: number;
  motorcycles: number;
  source?: string;
}

export interface TrafficSummary {
  total_vehicles_today: number;
  average_hourly: number;
  peak_hour: number;
  peak_count: number;
  roads_monitored: number;
  cameras_active: number;
  data_source: string;
}

export interface TrafficTimeline {
  date: string;
  data: HourlyDataPoint[];
  data_source: string;
}

export interface AffectedRoad {
  road_id: string;
  road_name: string;
  before_flow: number;
  after_flow: number;
  change_percent: number;
  capacity: number;
  utilization: number;
  status: string;
  delay_percent?: number;
}

export interface SimulationResult {
  simulation_id: string;
  closed_road: string;
  closed_road_name: string;
  closure_percentage: number;
  simulation_hour: number;
  displaced_vehicles: number;
  average_delay_percent: number;
  affected_roads: number;
  critical_roads: number;
  roads: AffectedRoad[];
  explanation: string;
  data_source: string;
}

export interface CompareResult {
  road_id: string;
  road_name: string;
  simulation_hour: number;
  scenarios: SimulationResult[];
}

export interface Scenario {
  id: string;
  road_id: string;
  road_name: string;
  closure_percentage: number;
  simulation_hour: number;
  displaced_vehicles: number;
  average_delay_percent: number;
  affected_roads_count: number;
  critical_roads_count: number;
  created_at: string | null;
}

// ─── API Functions ──────────────────────────────────────────────────

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'API Error');
  }
  return res.json();
}

// Health
export const getHealth = () => fetchJSON<{ status: string; version: string }>('/api/health');

// Roads
export const getRoads = () => fetchJSON<Road[]>('/api/roads');
export const getRoadDetail = (id: string) => fetchJSON<RoadDetail>(`/api/roads/${id}`);

// Intersections
export const getIntersections = () => fetchJSON<Intersection[]>('/api/intersections');

// Cameras
export const getCameras = () => fetchJSON<Camera[]>('/api/cameras');
export const getCameraDetail = (id: string) => fetchJSON<CameraDetail>(`/api/cameras/${id}`);
export const startCameraInference = (id: string) =>
  fetchJSON<CameraInference>(`/api/cameras/${id}/inference/start`, { method: 'POST' });
export const stopCameraInference = (id: string) =>
  fetchJSON<CameraInference>(`/api/cameras/${id}/inference/stop`, { method: 'POST' });
export const getCameraInference = (id: string) =>
  fetchJSON<CameraInference>(`/api/cameras/${id}/inference`);
export const getCameraInferenceVideoUrl = (id: string) =>
  `${API_BASE}/api/cameras/${id}/inference/video`;

// Traffic
export const getTrafficSummary = () => fetchJSON<TrafficSummary>('/api/traffic/summary');
export const getTrafficTimeline = () => fetchJSON<TrafficTimeline>('/api/traffic/timeline');
export const getTrafficByRoad = (roadId: string) =>
  fetchJSON<{ road_id: string; road_name: string; hourly_data: HourlyDataPoint[]; data_source: string }>(
    `/api/traffic/road/${roadId}`
  );

// Simulations
export const runSimulation = (roadId: string, closurePercentage: number, simulationHour: number = 8) =>
  fetchJSON<SimulationResult>('/api/simulations', {
    method: 'POST',
    body: JSON.stringify({
      road_id: roadId,
      closure_percentage: closurePercentage,
      simulation_hour: simulationHour,
    }),
  });

export const getSimulation = (id: string) => fetchJSON<SimulationResult>(`/api/simulations/${id}`);

export const compareSimulations = (
  roadId: string,
  closurePercentages: number[] = [25, 50, 75, 100],
  simulationHour: number = 8
) =>
  fetchJSON<CompareResult>('/api/simulations/compare', {
    method: 'POST',
    body: JSON.stringify({
      road_id: roadId,
      closure_percentages: closurePercentages,
      simulation_hour: simulationHour,
    }),
  });

// Scenarios
export const getScenarios = () => fetchJSON<Scenario[]>('/api/scenarios');
