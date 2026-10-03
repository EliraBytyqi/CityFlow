import React, { useMemo, useState } from 'react';
import { type Road, type Camera, type AffectedRoad } from '../services/api';

interface TrafficMapProps {
  roads: Road[];
  cameras?: Camera[];
  selectedRoadId: string | null;
  onSelectRoad: (roadId: string) => void;
  simulationResults?: AffectedRoad[] | null;
  closureRoadId?: string | null;
  closurePercentage?: number | null;
}

const loadColor = (utilization: number, closed: boolean) => {
  if (closed) return '#a8a69e';
  if (utilization < 0.5) return '#668c72';
  if (utilization < 0.75) return '#ab9547';
  if (utilization < 0.9) return '#b16d3d';
  return '#ad5550';
};

export const TrafficMap: React.FC<TrafficMapProps> = ({
  roads,
  cameras = [],
  selectedRoadId,
  onSelectRoad,
  simulationResults,
  closureRoadId,
  closurePercentage,
}) => {
  const [xRay, setXRay] = useState(true);
  const simulationByRoad = useMemo(() => new Map((simulationResults ?? []).map((road) => [road.road_id, road])), [simulationResults]);
  const geometry = useMemo(() => {
    const points = roads.flatMap((road) => road.geometry ?? []).filter(([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat));
    if (!points.length) return new Map<string, string>();
    const minLng = Math.min(...points.map(([lng]) => lng));
    const maxLng = Math.max(...points.map(([lng]) => lng));
    const minLat = Math.min(...points.map(([, lat]) => lat));
    const maxLat = Math.max(...points.map(([, lat]) => lat));
    const lngRange = maxLng - minLng || 1;
    const latRange = maxLat - minLat || 1;
    return new Map(roads.flatMap((road) => {
      if (!road.geometry || road.geometry.length < 2) return [];
      const path = road.geometry.map(([lng, lat], index) => {
        const x = 78 + ((lng - minLng) / lngRange) * 844;
        const y = 68 + ((maxLat - lat) / latRange) * 564;
        return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
      }).join(' ');
      return [[road.id, path] as const];
    }));
  }, [roads]);
  const nodePositions = useMemo(() => {
    const nodes = new Map<string, [number, number]>();
    roads.flatMap((road) => road.geometry ?? []).forEach(([lng, lat]) => {
      nodes.set(`${lng.toFixed(5)},${lat.toFixed(5)}`, [lng, lat]);
    });
    const points = [...nodes.values()];
    if (!points.length) return [];
    const minLng = Math.min(...points.map(([lng]) => lng));
    const maxLng = Math.max(...points.map(([lng]) => lng));
    const minLat = Math.min(...points.map(([, lat]) => lat));
    const maxLat = Math.max(...points.map(([, lat]) => lat));
    return points.map(([lng, lat]) => ({
      x: 78 + ((lng - minLng) / (maxLng - minLng || 1)) * 844,
      y: 68 + ((maxLat - lat) / (maxLat - minLat || 1)) * 564,
      key: `${lng}-${lat}`,
    }));
  }, [roads]);

  return (
    <div className={`network-map ${xRay ? 'xray-mode' : 'traffic-mode'}`}>
      <div className="network-map-grid" aria-hidden="true" />
      <div className="network-map-tools" role="group" aria-label="Network visualization mode">
        <span>VIEW</span>
        <button type="button" aria-pressed={!xRay} onClick={() => setXRay(false)}>TRAFFIC</button>
        <button type="button" aria-pressed={xRay} onClick={() => setXRay(true)}>X-RAY</button>
      </div>
      {roads.length === 0 || geometry.size === 0 ? (
        <div className="network-map-empty" role="status">Schematic network is loading or unavailable.</div>
      ) : (
        <svg className="network-svg" viewBox="0 0 1000 700" preserveAspectRatio="xMidYMid slice" role="img" aria-label={`Schematic network with ${roads.length} links and ${cameras.length} configured camera feeds`}>
          <defs>
            <filter id="road-halo" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="particle-halo" x="-300%" y="-300%" width="700%" height="700%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>
          <g className="network-lines">
            {roads.map((road) => {
              const path = geometry.get(road.id);
              if (!path) return null;
              const simulated = simulationByRoad.get(road.id);
              const utilization = simulated?.utilization ?? road.utilization;
              const closurePct = road.id === closureRoadId ? (closurePercentage ?? 100) : 0;
              const closed = (closurePct >= 100 && road.id === closureRoadId) || simulated?.status === 'closed';
              const closureOpacity = road.id === closureRoadId ? Math.max(.045, 1 - closurePct / 105) : 1;
              const color = loadColor(utilization, closed);
              const selected = road.id === selectedRoadId;
              const flow = simulated?.after_flow ?? road.current_flow;
              const particleCount = closed ? 0 : Math.max(1, Math.min(5, Math.round((flow / 650) * (1 - closurePct / 100))));
              const duration = Math.max(3, 15 - (Math.min(flow / Math.max(road.capacity, 1), 1.4) * 7));
              return (
                <g key={road.id} className={`network-link ${selected ? 'is-selected' : ''} ${closed ? 'is-closed' : ''}`} onClick={() => onSelectRoad(road.id)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectRoad(road.id); } }} role="button" tabIndex={0} aria-label={`${road.name}, ${Math.round(utilization * 100)} percent utilization${closed ? ', modeled closed' : ''}`}>
                  <title>{road.name} · {Math.round(utilization * 100)}% utilization{simulated ? ` · modeled flow ${simulated.after_flow}` : ''}</title>
                  {selected && <path d={path} className="link-selected-halo" />}
                  <path id={`flow-${road.id}`} d={path} className="link-halo" stroke={color} style={{ opacity: .17 * closureOpacity }} />
                  <path d={path} className="link-core" stroke={color} style={{ opacity: .82 * closureOpacity }} />
                  {particleCount > 0 && Array.from({ length: particleCount }, (_, index) => (
                  <circle key={`${road.id}-particle-${index}`} className="flow-particle" r={selected ? 2.8 : 2.2} fill={selected ? '#315c4c' : color}>
                      <animateMotion dur={`${duration.toFixed(1)}s`} begin={`${-(duration * index / particleCount).toFixed(1)}s`} repeatCount="indefinite" rotate="auto">
                        <mpath href={`#flow-${road.id}`} />
                      </animateMotion>
                    </circle>
                  ))}
                </g>
              );
            })}
          </g>
          <g className="network-nodes" aria-hidden="true">
            {nodePositions.map(({ x, y, key }) => <g key={key} transform={`translate(${x},${y})`}><circle r="9" className="node-halo" /><circle r="3.5" className="network-node" /></g>)}
          </g>
        </svg>
      )}
    </div>
  );
};
