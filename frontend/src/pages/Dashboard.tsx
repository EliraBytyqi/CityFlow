import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { WhatIfPanel } from '../components/WhatIfPanel';
import { BeforeAfterView } from '../components/BeforeAfterView';
import { AIExplanationCard } from '../components/AIExplanationCard';
import { TrafficMap } from '../components/TrafficMap';
import {
  type Road, type Camera, type TrafficSummary, type SimulationResult,
  getRoads, getCameras, getTrafficSummary, runSimulation,
} from '../services/api';
import { Activity, AlertTriangle, ArrowDownRight, ArrowRight, Camera as CameraIcon, Clock3 } from 'lucide-react';

interface DashboardProps {
  simulationResult: SimulationResult | null;
  setSimulationResult: (result: SimulationResult | null) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ simulationResult, setSimulationResult }) => {
  const [roads, setRoads] = useState<Road[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [summary, setSummary] = useState<TrafficSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [selectedRoadId, setSelectedRoadId] = useState('road_01');
  const [closurePreview, setClosurePreview] = useState<{ roadId: string; percentage: number } | null>(null);
  const selectedRoad = roads.find((road) => road.id === selectedRoadId) ?? roads[0] ?? null;

  useEffect(() => {
    let cancelled = false;
    Promise.all([getRoads(), getCameras(), getTrafficSummary()])
      .then(([roadData, cameraData, trafficSummary]) => {
        if (cancelled) return;
        setRoads(roadData);
        setCameras(cameraData.filter((camera) => camera.stream_url));
        setSummary(trafficSummary);
      })
      .catch((error: Error) => { if (!cancelled) setLoadError(error.message); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const handleSimulate = async (roadId: string, closurePercentage: number, hour: number) => {
    setIsSimulating(true);
    setSimulationError(null);
    try {
      setSimulationResult(await runSimulation(roadId, closurePercentage, hour));
      setClosurePreview({ roadId, percentage: closurePercentage });
    } catch (error) {
      setSimulationError(error instanceof Error ? error.message : 'The model could not run this scenario.');
    } finally {
      setIsSimulating(false);
    }
  };

  const dataSourceLabel = summary?.data_source === 'observed'
    ? 'OBSERVED COUNTS'
    : summary?.data_source === 'mixed' ? 'SAMPLE + LIVE COUNTS' : summary ? 'SAMPLE BASELINE' : isLoading ? 'LOADING DATA' : 'DATA UNAVAILABLE';

  return (
    <div className="page-view command-view">
      <main className={`command-stage ${simulationResult ? 'has-impact' : ''}`}>
        <div className="command-map" aria-label="Schematic traffic network visualization">
          <TrafficMap
            roads={roads}
            cameras={cameras}
            selectedRoadId={selectedRoad?.id ?? null}
            onSelectRoad={(roadId) => { setSelectedRoadId(roadId); setClosurePreview(null); }}
            simulationResults={simulationResult?.roads}
            closureRoadId={closurePreview?.roadId ?? simulationResult?.closed_road}
            closurePercentage={closurePreview?.percentage ?? simulationResult?.closure_percentage}
          />
        </div>

        <section className="command-heading" aria-label="City pulse">
          <div className="command-kicker"><span className="tiny-pulse" /> CITY PULSE <span className="command-divider">/</span> KOSOVO</div>
          <h1>See the city.<br /><em>Understand the data.</em></h1>
          <p>Traffic as a living network. Select a road and model what a closure could change.</p>
        </section>

        {loadError && <div role="alert" className="command-alert"><AlertTriangle size={15} /> City data unavailable: {loadError}</div>}

        <section className="command-volume" aria-label="Traffic volume summary">
          <div className="hud-panel-heading"><span>TRAFFIC VOLUME</span><span>24H</span></div>
          <div className="command-volume-number">{isLoading ? '···' : summary ? summary.total_vehicles_today.toLocaleString() : '—'}</div>
          <div className="command-volume-unit">VEHICLES <span>·</span> {dataSourceLabel}</div>
          <div className="command-volume-meta">
            <span><Activity size={13} /> {isLoading ? '—' : (summary?.average_hourly ?? 0).toLocaleString()} / HR AVG</span>
            <span><Clock3 size={13} /> PEAK {summary ? `${String(summary.peak_hour).padStart(2, '0')}:00` : '—'}</span>
          </div>
          <div className="pulse-time-track" aria-label={summary ? `Peak hour is ${String(summary.peak_hour).padStart(2, '0')}:00` : 'Peak hour unavailable'}>
            <span>00:00</span><div className="pulse-time-line">{summary && <i style={{ left: `${(summary.peak_hour / 23) * 100}%` }}><b>{String(summary.peak_hour).padStart(2, '0')}:00 PEAK</b></i>}</div><span>23:00</span>
          </div>
          <div className="command-volume-source">Baseline labels stay visible so sample and observed counts are clear.</div>
        </section>

        <aside className="command-controls" aria-label="Traffic scenario controls">
          <div className="command-controls-top"><span className="command-kicker">WHAT IF?</span><span className="command-live-state"><i /> ON-DEMAND MODEL</span></div>
          <WhatIfPanel
            selectedRoad={selectedRoad}
            onSimulate={handleSimulate}
            isSimulating={isSimulating}
            onClosurePreview={(roadId, percentage) => setClosurePreview({ roadId, percentage })}
          />
          {simulationError && <div role="alert" className="command-sim-error"><AlertTriangle size={14} /> {simulationError}</div>}
          <div className="command-model-note">SIMULATED OUTPUT <span>Uses the sample network model. Not a surveyed Kosovo road graph.</span></div>
        </aside>

        <div className="command-network-state">
          <span><i className="state-dot state-cyan" /> {loadError && cameras.length === 0 ? '—' : cameras.length.toString().padStart(2, '0')} FEEDS CONFIGURED</span>
          <span><i className="state-dot state-cyan" /> {loadError && roads.length === 0 ? '—' : roads.length.toString().padStart(2, '0')} NETWORK LINKS</span>
          <Link to="/cameras"><CameraIcon size={13} /> OPEN CAMERAS <ArrowRight size={12} /></Link>
        </div>

        <div className="command-legend" aria-label="Traffic utilization legend">
          <span className="legend-title">NETWORK LOAD</span>
          <span><i className="state-dot state-low" /> LOW</span>
          <span><i className="state-dot state-moderate" /> MODERATE</span>
          <span><i className="state-dot state-high" /> HIGH</span>
          <span><i className="state-dot state-critical" /> CRITICAL</span>
          <span className="legend-schematic">SCHEMATIC</span>
        </div>

        {simulationResult && (
          <section className="command-impact" aria-live="polite" aria-label="Modeled scenario impact">
            <div className="command-impact-title"><span>MODELED IMPACT</span><small>{simulationResult.closed_road_name} · {simulationResult.closure_percentage}% CLOSED</small></div>
            <div className="command-impact-metric"><strong>{simulationResult.displaced_vehicles.toLocaleString()}</strong><span>VEHICLES REDIRECTED</span></div>
            <div className="command-impact-metric"><strong>+{simulationResult.average_delay_percent}%</strong><span>AVERAGE DELAY</span></div>
            <div className="command-impact-metric"><strong>{simulationResult.critical_roads}</strong><span>CRITICAL LINKS</span></div>
            <div className="command-impact-time"><ArrowDownRight size={16} /> PEAK MODEL HOUR <b>{String(simulationResult.simulation_hour).padStart(2, '0')}:00</b></div>
          </section>
        )}

        <div className="command-map-caption">SCHEMATIC NETWORK <span>·</span> LINKS ARE MODEL GEOMETRY, NOT LIVE GIS ROADS</div>
      </main>

      {simulationResult && (
        <details className="command-impact-details">
          <summary>Inspect modeled route-by-route changes <ArrowRight size={14} /></summary>
          <BeforeAfterView simulation={simulationResult} />
          <AIExplanationCard explanation={simulationResult.explanation} />
        </details>
      )}
    </div>
  );
};
