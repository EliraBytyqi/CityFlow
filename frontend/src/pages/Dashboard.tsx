import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { TrafficMap } from '../components/TrafficMap';
import { WhatIfPanel } from '../components/WhatIfPanel';
import { BeforeAfterView } from '../components/BeforeAfterView';
import { AIExplanationCard } from '../components/AIExplanationCard';
import { DataSourceBadge } from '../components/DataSourceBadge';
import {
  type Road,
  type Camera,
  type TrafficSummary,
  type SimulationResult,
  getRoads,
  getCameras,
  getTrafficSummary,
  runSimulation,
  getRoadDetail,
} from '../services/api';
import { Car, BarChart2, Clock, Camera as CameraIcon, MapPin, X } from 'lucide-react';

interface DashboardProps {
  selectedRoadId: string | null;
  setSelectedRoadId: (id: string | null) => void;
  simulationResult: SimulationResult | null;
  setSimulationResult: (result: SimulationResult | null) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  selectedRoadId,
  setSelectedRoadId,
  simulationResult,
  setSimulationResult,
}) => {
  const [roads, setRoads] = useState<Road[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [summary, setSummary] = useState<TrafficSummary | null>(null);
  const [selectedRoad, setSelectedRoad] = useState<Road | null>(null);
  const [roadDetail, setRoadDetail] = useState<any | null>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [rData, cData, sData] = await Promise.all([
          getRoads(),
          getCameras(),
          getTrafficSummary(),
        ]);
        setRoads(rData);
        setCameras(cData);
        setSummary(sData);

        // Auto-select Weststraat (road_01) by default if available
        if (!selectedRoadId && rData.length > 0) {
          const west = rData.find((r) => r.name.toLowerCase().includes('weststraat')) || rData[0];
          setSelectedRoadId(west.id);
        }
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      }
    };
    fetchData();
  }, []);

  // Update selected road detail when selectedRoadId changes
  useEffect(() => {
    if (!selectedRoadId) {
      setSelectedRoad(null);
      setRoadDetail(null);
      return;
    }

    const road = roads.find((r) => r.id === selectedRoadId);
    if (road) setSelectedRoad(road);

    getRoadDetail(selectedRoadId)
      .then((detail) => setRoadDetail(detail))
      .catch((err) => console.error('Failed to fetch road detail:', err));
  }, [selectedRoadId, roads]);

  const handleSimulate = async (roadId: string, closurePercentage: number, hour: number) => {
    setIsSimulating(true);
    try {
      const res = await runSimulation(roadId, closurePercentage, hour);
      setSimulationResult(res);
    } catch (err) {
      console.error('Simulation error:', err);
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        title="CITYFLOW AI"
        subtitle="See the impact before you change the street."
        dataSource={summary?.data_source || 'demo'}
      />

      <main className="p-8 flex flex-col gap-6 flex-1 max-w-[1600px] w-full mx-auto">
        {/* Top Indicators */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="glass-card stat-card">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
              <Car className="w-4 h-4 text-indigo-400" />
              Vehicles Today
            </div>
            <div className="stat-value font-mono mt-1">
              {summary ? summary.total_vehicles_today.toLocaleString() : '---'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">24h Monitored Flow</div>
          </div>

          <div className="glass-card stat-card">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
              <BarChart2 className="w-4 h-4 text-cyan-400" />
              Avg Hourly Flow
            </div>
            <div className="stat-value font-mono mt-1">
              {summary ? summary.average_hourly.toLocaleString() : '---'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">veh/hour</div>
          </div>

          <div className="glass-card stat-card">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
              <Clock className="w-4 h-4 text-amber-400" />
              Peak Hour
            </div>
            <div className="stat-value font-mono mt-1">
              {summary ? `${summary.peak_hour.toString().padStart(2, '0')}:00` : '---'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">
              {summary ? `${summary.peak_count.toLocaleString()} veh/hr` : '---'}
            </div>
          </div>

          <div className="glass-card stat-card">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
              <MapPin className="w-4 h-4 text-emerald-400" />
              Roads Monitored
            </div>
            <div className="stat-value font-mono mt-1">
              {summary ? summary.roads_monitored : '---'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">Network Arcs</div>
          </div>

          <div className="glass-card stat-card">
            <div className="flex items-center gap-2 text-slate-400 text-xs font-semibold uppercase">
              <CameraIcon className="w-4 h-4 text-purple-400" />
              AI Cameras
            </div>
            <div className="stat-value font-mono mt-1">
              {summary ? summary.cameras_active : '---'}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">Active Streams</div>
          </div>
        </div>

        {/* Main Centerpiece Layout: Map (65%) + What-If Panel (35%) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Map Column (7 cols ≈ 60-65%) */}
          <div className="lg:col-span-7 flex flex-col gap-4">
            <div className="glass-card p-4 rounded-2xl flex flex-col gap-3">
              <div className="flex items-center justify-between px-2">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wide">
                    ROAD NETWORK MAP
                  </h3>
                  <DataSourceBadge source={summary?.data_source || 'demo'} />
                </div>
                <span className="text-xs text-slate-400">Click any road to inspect or simulate</span>
              </div>

              <TrafficMap
                roads={roads}
                cameras={cameras}
                selectedRoadId={selectedRoadId}
                onSelectRoad={(id) => setSelectedRoadId(id)}
                simulationResults={simulationResult?.roads}
                closureRoadId={simulationResult?.closed_road}
              />
            </div>

            {/* Selected Road Details Popover Card */}
            {roadDetail && (
              <div className="glass-card p-5 rounded-2xl border border-indigo-500/30 flex flex-col gap-3 relative animate-fade-in">
                <button
                  type="button"
                  onClick={() => setSelectedRoadId(null)}
                  className="absolute top-4 right-4 text-slate-500 hover:text-slate-200"
                >
                  <X className="w-4 h-4" />
                </button>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-400 uppercase">ROAD DETAILS</span>
                  <DataSourceBadge source={roadDetail.data_source} />
                </div>
                <div className="text-lg font-bold text-slate-100">{roadDetail.name}</div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs pt-2 border-t border-slate-800">
                  <div>
                    <span className="text-slate-400">Traffic:</span>
                    <div className="font-bold text-slate-100 text-sm">{roadDetail.current_flow.toLocaleString()} veh/day</div>
                  </div>
                  <div>
                    <span className="text-slate-400">Capacity:</span>
                    <div className="font-bold text-slate-100 text-sm">{roadDetail.capacity.toLocaleString()} veh/day</div>
                  </div>
                  <div>
                    <span className="text-slate-400">Utilization:</span>
                    <div className="font-bold text-indigo-400 text-sm">{Math.round(roadDetail.utilization * 100)}%</div>
                  </div>
                  <div>
                    <span className="text-slate-400">Avg Speed:</span>
                    <div className="font-bold text-emerald-400 text-sm">{roadDetail.average_speed} km/h</div>
                  </div>
                </div>
                {roadDetail.camera_name && (
                  <div className="text-[11px] text-slate-400 pt-1 flex items-center gap-1.5">
                    <CameraIcon className="w-3.5 h-3.5 text-cyan-400" />
                    Source: <span className="font-semibold text-slate-200">{roadDetail.camera_name}</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Right Column: Simulator & Results (5 cols ≈ 35-40%) */}
          <div className="lg:col-span-5 flex flex-col gap-6">
            <WhatIfPanel
              selectedRoad={selectedRoad}
              onSimulate={handleSimulate}
              isSimulating={isSimulating}
            />

            {/* Simulation Results Section */}
            <BeforeAfterView simulation={simulationResult} />

            {/* AI Natural Language Explanation */}
            <AIExplanationCard explanation={simulationResult?.explanation || null} />
          </div>
        </div>
      </main>
    </div>
  );
};
