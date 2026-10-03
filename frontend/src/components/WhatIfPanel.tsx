import React, { useState } from 'react';
import { Play, Clock, AlertTriangle, Layers } from 'lucide-react';
import { type Road } from '../services/api';

interface WhatIfPanelProps {
  selectedRoad: Road | null;
  onSimulate: (roadId: string, closurePercentage: number, hour: number) => void;
  isSimulating: boolean;
}

export const WhatIfPanel: React.FC<WhatIfPanelProps> = ({
  selectedRoad,
  onSimulate,
  isSimulating,
}) => {
  const [closurePct, setClosurePct] = useState<number>(100);
  const [selectedHour, setSelectedHour] = useState<number>(8);
  const [loadingStep, setLoadingStep] = useState<string>('');

  const hours = [6, 8, 10, 12, 14, 16, 18, 20];
  const closures = [25, 50, 75, 100];

  const handleRunSimulation = () => {
    if (!selectedRoad) return;

    // Simulate animated loading states
    setLoadingStep('Analyzing traffic network...');
    setTimeout(() => setLoadingStep('Calculating alternative routes...'), 400);
    setTimeout(() => setLoadingStep('Redistributing traffic...'), 800);
    setTimeout(() => setLoadingStep('Calculating congestion & delays...'), 1200);

    setTimeout(() => {
      onSimulate(selectedRoad.id, closurePct, selectedHour);
      setLoadingStep('');
    }, 1500);
  };

  return (
    <div className="glass-card whatif-panel rounded-2xl flex flex-col gap-5 border border-indigo-500/20 bg-slate-900/60 backdrop-blur-xl p-6 shadow-2xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 tracking-tight">WHAT IF?</h2>
            <p className="text-xs text-slate-400">Simulate road network modifications in real time</p>
          </div>
        </div>
      </div>

      {/* Selected Road Card */}
      {selectedRoad ? (
        <div className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/50 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Selected Road</span>
            <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-mono">
              {selectedRoad.id}
            </span>
          </div>
          <div className="text-base font-bold text-slate-100">{selectedRoad.name}</div>
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 pt-1 border-t border-slate-700/40">
            <div>Capacity: <span className="font-semibold text-slate-200">{selectedRoad.capacity.toLocaleString()} veh/day</span></div>
            <div>Current Flow: <span className="font-semibold text-slate-200">{selectedRoad.current_flow.toLocaleString()} veh/day</span></div>
          </div>
        </div>
      ) : (
        <div className="p-4 rounded-xl bg-slate-800/30 border border-dashed border-slate-700/60 text-center text-xs text-slate-400 flex items-center justify-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>Click any road on the map to select it</span>
        </div>
      )}

      {/* Closure Percentage Selection */}
      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
          Closure Level
        </label>
        <div className="grid grid-cols-4 gap-2">
          {closures.map((pct) => (
            <button
              key={pct}
              type="button"
              onClick={() => setClosurePct(pct)}
              className={`btn-closure ${closurePct === pct ? 'active' : ''}`}
            >
              {pct}%
            </button>
          ))}
        </div>
      </div>

      {/* Time-Based Simulation Selection */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            Simulation Hour
          </label>
          <span className="text-xs font-mono font-bold text-indigo-400">
            {selectedHour.toString().padStart(2, '0')}:00
          </span>
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {hours.map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setSelectedHour(h)}
              className={`py-1.5 px-2 text-xs font-medium rounded-lg border transition-all ${
                selectedHour === h
                  ? 'bg-indigo-600/30 border-indigo-500 text-indigo-200 font-bold'
                  : 'bg-slate-800/40 border-slate-700/40 text-slate-400 hover:border-slate-600'
              }`}
            >
              {h.toString().padStart(2, '0')}:00
            </button>
          ))}
        </div>
      </div>

      {/* Animated Loading State or Simulate Button */}
      {isSimulating || loadingStep ? (
        <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex flex-col items-center gap-3 animate-pulse">
          <div className="loading-spinner" />
          <span className="text-xs font-semibold text-indigo-300 tracking-wide">{loadingStep}</span>
        </div>
      ) : (
        <button
          type="button"
          onClick={handleRunSimulation}
          disabled={!selectedRoad}
          className="btn-primary w-full py-3.5 shadow-lg shadow-indigo-500/20"
        >
          <Play className="w-4 h-4 fill-current" />
          SIMULATE CLOSURE
        </button>
      )}
    </div>
  );
};
