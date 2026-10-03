import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import { type Road, type Camera, type AffectedRoad } from '../services/api';

interface TrafficMapProps {
  roads: Road[];
  cameras?: Camera[];
  selectedRoadId: string | null;
  onSelectRoad: (roadId: string) => void;
  simulationResults?: AffectedRoad[] | null;
  closureRoadId?: string | null;
}

const getUtilizationColor = (utilization: number, isClosed: boolean = false): string => {
  if (isClosed) return '#6b7280'; // gray for closed
  if (utilization < 0.50) return '#22c55e'; // GREEN
  if (utilization < 0.75) return '#eab308'; // YELLOW
  if (utilization < 0.90) return '#f97316'; // ORANGE
  return '#ef4444'; // RED
};

export const TrafficMap: React.FC<TrafficMapProps> = ({
  roads,
  cameras = [],
  selectedRoadId,
  onSelectRoad,
  simulationResults,
  closureRoadId,
}) => {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const layersRef = useRef<L.LayerGroup | null>(null);

  // Initialize Leaflet map
  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;

    // Centered around our demo city (Delft-like coordinates: 52.013, 4.358)
    const map = L.map(mapRef.current, {
      center: [52.013, 4.358],
      zoom: 14,
      zoomControl: true,
      attributionControl: false,
    });

    // Dark tile layer (CartoDB Dark Matter)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
      subdomains: 'abcd',
    }).addTo(map);

    const layerGroup = L.layerGroup().addTo(map);
    layersRef.current = layerGroup;
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update map polylines & markers when props change
  useEffect(() => {
    const map = mapInstanceRef.current;
    const layerGroup = layersRef.current;
    if (!map || !layerGroup) return;

    layerGroup.clearLayers();

    // Create lookup for simulation outputs
    const simMap = new Map<string, AffectedRoad>();
    if (simulationResults) {
      simulationResults.forEach((r) => simMap.set(r.road_id, r));
    }

    // Render Roads
    roads.forEach((road) => {
      if (!road.geometry || road.geometry.length < 2) return;

      // Leaflet expects [lat, lng] array
      const latLngs: L.LatLngExpression[] = road.geometry.map(([lng, lat]) => [lat, lng]);

      const isSelected = road.id === selectedRoadId;
      const isClosed = road.id === closureRoadId;
      const simData = simMap.get(road.id);

      let utilization = road.utilization;
      let status = road.status;

      if (simData) {
        utilization = simData.utilization;
        status = simData.status;
      }

      const strokeColor = isClosed ? '#6b7280' : getUtilizationColor(utilization, status === 'closed');
      const strokeWidth = isSelected ? 8 : 5;
      const opacity = isSelected ? 1.0 : 0.8;

      const polyline = L.polyline(latLngs, {
        color: strokeColor,
        weight: strokeWidth,
        opacity: opacity,
        dashArray: isClosed ? '8, 8' : undefined,
        lineCap: 'round',
        lineJoin: 'round',
      });

      // Hover and click interactions
      polyline.on('click', () => {
        onSelectRoad(road.id);
      });

      polyline.on('mouseover', (e) => {
        const layer = e.target;
        layer.setStyle({ weight: strokeWidth + 3, opacity: 1.0 });
      });

      polyline.on('mouseout', (e) => {
        const layer = e.target;
        layer.setStyle({ weight: strokeWidth, opacity: opacity });
      });

      // Tooltip / Popup content
      const popupContent = `
        <div style="font-family: 'Inter', sans-serif;">
          <div style="font-weight: 700; font-size: 14px; margin-bottom: 4px;">${road.name}</div>
          <div style="color: #94a3b8; font-size: 12px; margin-bottom: 6px;">ID: ${road.id} | ${road.road_type.toUpperCase()}</div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>Flow:</span>
            <span style="font-weight: 600;">${simData ? simData.after_flow : road.current_flow} veh/hr</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span>Capacity:</span>
            <span style="font-weight: 600;">${road.capacity} veh/hr</span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
            <span>Utilization:</span>
            <span style="font-weight: 700; color: ${strokeColor};">${Math.round(utilization * 100)}%</span>
          </div>
          ${
            simData && simData.change_percent !== 0
              ? `<div style="font-size: 11px; padding: 4px 6px; border-radius: 4px; background: rgba(99,102,241,0.1); color: #818cf8; text-align: center; margin-top: 6px;">
                   Traffic Change: ${simData.change_percent > 0 ? '+' : ''}${simData.change_percent}%
                 </div>`
              : ''
          }
        </div>
      `;

      polyline.bindPopup(popupContent);
      layerGroup.addLayer(polyline);

      // Selected road glow highlight ring
      if (isSelected) {
        const glowPolyline = L.polyline(latLngs, {
          color: '#6366f1',
          weight: strokeWidth + 6,
          opacity: 0.3,
        });
        layerGroup.addLayer(glowPolyline);
      }
    });

    // Render Camera Markers
    cameras.forEach((cam) => {
      const cameraIcon = L.divIcon({
        className: 'custom-camera-icon',
        html: `
          <div style="
            width: 26px;
            height: 26px;
            background: rgba(17, 24, 39, 0.9);
            border: 2px solid #06b6d4;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 10px rgba(6, 182, 212, 0.5);
            color: #06b6d4;
            font-size: 12px;
          ">
            📷
          </div>
        `,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      });

      const marker = L.marker([cam.latitude, cam.longitude], { icon: cameraIcon });
      marker.bindPopup(`
        <div style="font-family: 'Inter', sans-serif;">
          <div style="font-weight: 700; color: #06b6d4;">${cam.name}</div>
          <div style="font-size: 11px; color: #94a3b8;">${cam.id} — ONLINE</div>
          <div style="margin-top: 4px; font-size: 12px;">Road: ${cam.road_name || cam.road_id || 'N/A'}</div>
          ${cam.vehicles_per_hour ? `<div style="font-size: 12px; font-weight: 600; margin-top: 2px;">Peak: ${cam.vehicles_per_hour} veh/hr</div>` : ''}
        </div>
      `);
      layerGroup.addLayer(marker);
    });
  }, [roads, cameras, selectedRoadId, simulationResults, closureRoadId, onSelectRoad]);

  return (
    <div className="map-container relative h-full min-h-[450px]">
      <div ref={mapRef} className="w-full h-full min-h-[450px]" />

      {/* Map Legend Overlay */}
      <div className="absolute bottom-4 left-4 z-[1000] glass-card p-3 text-xs flex flex-col gap-1.5 backdrop-blur-md bg-slate-900/80 border border-slate-700/50 rounded-xl">
        <div className="font-semibold text-slate-300 mb-1">UTILIZATION KEY</div>
        <div className="flex items-center gap-2 text-slate-400">
          <span className="w-3 h-3 rounded-full bg-[#22c55e]" /> &lt;50% (Low)
        </div>
        <div className="flex items-center gap-2 text-slate-400">
          <span className="w-3 h-3 rounded-full bg-[#eab308]" /> 50–75% (Moderate)
        </div>
        <div className="flex items-center gap-2 text-slate-400">
          <span className="w-3 h-3 rounded-full bg-[#f97316]" /> 75–90% (High)
        </div>
        <div className="flex items-center gap-2 text-slate-400">
          <span className="w-3 h-3 rounded-full bg-[#ef4444]" /> &gt;90% (Critical)
        </div>
        <div className="flex items-center gap-2 text-slate-400">
          <span className="w-3 h-1 bg-[#6b7280] rounded" /> Closed / Blocked
        </div>
      </div>
    </div>
  );
};
