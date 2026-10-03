import React from 'react';
import { ArrowRight, AlertCircle, TrendingUp, Clock, ShieldAlert } from 'lucide-react';
import { type SimulationResult } from '../services/api';
import { DataSourceBadge } from './DataSourceBadge';

interface BeforeAfterViewProps {
  simulation: SimulationResult | null;
}

export const BeforeAfterView: React.FC<BeforeAfterViewProps> = ({ simulation }) => {
  if (!simulation) {
    return (
      <div className="glass-card p-6 text-center text-slate-500 border border-slate-800 rounded-2xl flex flex-col items-center justify-center min-h-[300px] gap-3">
        <TrendingUp className="w-8 h-8 text-slate-600" />
        <div className="text-sm font-medium">No Simulation Active</div>
        <div className="text-xs max-w-xs text-slate-600">
          Select a road and click "SIMULATE CLOSURE" to observe traffic redistribution.
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card-solid p-6 rounded-2xl border border-indigo-500/20 flex flex-col gap-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-700/50 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-slate-100">BEFORE / AFTER IMPACT ANALYSIS</h3>
            <DataSourceBadge source="simulated" />
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Modeled redistribution after {simulation.closure_percentage}% closure of{' '}
            <span className="font-semibold text-slate-200">{simulation.closed_road_name}</span> at{' '}
            <span className="font-mono text-indigo-400">{simulation.simulation_hour.toString().padStart(2, '0')}:00</span>
          </p>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/40">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
            Vehicles Displaced
          </div>
          <div className="text-2xl font-extrabold text-indigo-400 font-mono">
            {simulation.displaced_vehicles.toLocaleString()}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">veh/hour</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/40">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            Average Delay
          </div>
          <div className="text-2xl font-extrabold text-amber-400 font-mono">
            +{simulation.average_delay_percent}%
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">travel time increase</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/40">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
            Affected Roads
          </div>
          <div className="text-2xl font-extrabold text-cyan-400 font-mono">
            {simulation.affected_roads}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">routes re-routed</div>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-800/50 border border-slate-700/40">
          <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-1">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
            Critical Roads
          </div>
          <div className="text-2xl font-extrabold text-rose-400 font-mono">
            {simulation.critical_roads}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">&gt;90% capacity</div>
        </div>
      </div>

      {/* Comparison Table & Animated Bars */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between text-xs font-semibold text-slate-400 px-2 uppercase tracking-wider border-b border-slate-800 pb-2">
          <span>ROAD NAME</span>
          <div className="flex items-center gap-8">
            <span>CURRENT</span>
            <span className="text-indigo-400">SIMULATED</span>
            <span>CHANGE</span>
          </div>
        </div>

        <div className="flex flex-col gap-2 max-h-[280px] overflow-y-auto pr-1">
          {simulation.roads.map((road) => {
            const isClosed = road.road_id === simulation.closed_road;
            const maxVal = Math.max(road.before_flow, road.after_flow, 1);
            const beforeWidth = Math.min((road.before_flow / (road.capacity || maxVal)) * 100, 100);
            const afterWidth = Math.min((road.after_flow / (road.capacity || maxVal)) * 100, 100);

            return (
              <div
                key={road.road_id}
                className={`p-3 rounded-xl border transition-all ${
                  isClosed
                    ? 'bg-rose-950/20 border-rose-500/30'
                    : road.status === 'critical'
                    ? 'bg-amber-950/20 border-amber-500/30'
                    : 'bg-slate-800/30 border-slate-700/30'
                }`}
              >
                <div className="flex items-center justify-between text-xs font-medium text-slate-200 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100">{road.road_name}</span>
                    {isClosed && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold uppercase">
                        Closed
                      </span>
                    )}
                    {road.status === 'critical' && !isClosed && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold uppercase">
                        Critical
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-6 font-mono text-xs">
                    <span className="text-slate-400">{road.before_flow}</span>
                    <ArrowRight className="w-3 h-3 text-slate-600" />
                    <span className="font-bold text-indigo-300">{road.after_flow}</span>
                    <span
                      className={`font-semibold min-w-[50px] text-right ${
                        road.change_percent > 0
                          ? 'text-rose-400'
                          : road.change_percent < 0
                          ? 'text-emerald-400'
                          : 'text-slate-400'
                      }`}
                    >
                      {road.change_percent > 0 ? '+' : ''}
                      {road.change_percent}%
                    </span>
                  </div>
                </div>

                {/* Animated Comparison Bars */}
                <div className="grid grid-cols-2 gap-2 mt-1">
                  <div className="flex flex-col gap-0.5">
                    <div className="text-[9px] text-slate-500 uppercase">Before</div>
                    <div className="comparison-bar">
                      <div
                        className="comparison-bar-fill bg-slate-600"
                        style={{ width: `${beforeWidth}%` }}
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-0.5">
                    <div className="text-[9px] text-indigo-400 uppercase">After</div>
                    <div className="comparison-bar">
                      <div
                        className={`comparison-bar-fill ${
                          isClosed
                            ? 'bg-rose-500'
                            : road.status === 'critical'
                            ? 'bg-amber-500'
                            : 'bg-indigo-500'
                        }`}
                        style={{ width: `${afterWidth}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
