import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { DataSourceBadge } from '../components/DataSourceBadge';
import { getRoads, compareSimulations, type Road, type CompareResult } from '../services/api';
import { GitCompare, ArrowUpRight, ShieldAlert, Clock, AlertCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const Scenarios: React.FC = () => {
  const [roads, setRoads] = useState<Road[]>([]);
  const [selectedRoadId, setSelectedRoadId] = useState<string>('road_01');
  const [comparison, setComparison] = useState<CompareResult | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    getRoads().then((rData) => {
      setRoads(rData);
      if (rData.length > 0) {
        const defaultRoad = rData.find((r) => r.name.toLowerCase().includes('weststraat')) || rData[0];
        setSelectedRoadId(defaultRoad.id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedRoadId) return;
    setIsLoading(true);
    compareSimulations(selectedRoadId, [25, 50, 75, 100], 8)
      .then((res) => setComparison(res))
      .catch((err) => console.error('Comparison failed:', err))
      .finally(() => setIsLoading(false));
  }, [selectedRoadId]);

  const chartData = comparison?.scenarios.map((s) => ({
    closure: `${s.closure_percentage}% Closure`,
    displaced: s.displaced_vehicles,
    delay: s.average_delay_percent,
    affected: s.affected_roads,
    critical: s.critical_roads,
  }));

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        title="SCENARIO COMPARISON"
        subtitle="Evaluate trade-offs across closure levels and multi-street configurations"
      />

      <main className="p-8 flex flex-col gap-6 flex-1 max-w-[1600px] w-full mx-auto">
        {/* Road Selector Bar */}
        <div className="glass-card p-4 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <GitCompare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
                SELECT ROAD TO COMPARE
              </h3>
              <p className="text-xs text-slate-400">Side-by-side analysis of 25%, 50%, 75%, and 100% closure levels</p>
            </div>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <select
              value={selectedRoadId}
              onChange={(e) => setSelectedRoadId(e.target.value)}
              className="bg-slate-900 text-slate-100 border border-slate-700/60 rounded-xl px-4 py-2.5 text-xs font-semibold focus:outline-none focus:border-indigo-500 w-full sm:w-[260px]"
            >
              {roads.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name} ({r.current_flow.toLocaleString()} veh/day)
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Side-by-Side Comparison Cards */}
        {isLoading ? (
          <div className="p-12 text-center flex items-center justify-center">
            <div className="loading-spinner" />
          </div>
        ) : comparison ? (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 animate-fade-in">
            {comparison.scenarios.map((sc) => (
              <div
                key={sc.closure_percentage}
                className="glass-card p-5 rounded-2xl flex flex-col gap-4 border border-slate-700/50 hover:border-indigo-500/40 transition-all"
              >
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <span className="text-lg font-black text-indigo-400 font-mono">
                    {sc.closure_percentage}% CLOSURE
                  </span>
                  <DataSourceBadge source="simulated" />
                </div>

                <div className="flex flex-col gap-3">
                  <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/40">
                    <div className="text-[10px] text-slate-400 font-semibold uppercase flex items-center gap-1">
                      <AlertCircle className="w-3 h-3 text-amber-400" /> Displaced Vehicles
                    </div>
                    <div className="text-xl font-bold text-slate-100 font-mono mt-1">
                      {sc.displaced_vehicles.toLocaleString()} <span className="text-xs text-slate-500">veh/hr</span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/40">
                    <div className="text-[10px] text-slate-400 font-semibold uppercase flex items-center gap-1">
                      <Clock className="w-3 h-3 text-indigo-400" /> Modeled Delay
                    </div>
                    <div className="text-xl font-bold text-amber-400 font-mono mt-1">
                      +{sc.average_delay_percent}%
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/40">
                    <div className="text-[10px] text-slate-400 font-semibold uppercase flex items-center gap-1">
                      <ArrowUpRight className="w-3 h-3 text-cyan-400" /> Affected Roads
                    </div>
                    <div className="text-xl font-bold text-cyan-400 font-mono mt-1">
                      {sc.affected_roads}
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-slate-800/40 border border-slate-700/40">
                    <div className="text-[10px] text-slate-400 font-semibold uppercase flex items-center gap-1">
                      <ShieldAlert className="w-3 h-3 text-rose-400" /> Critical Corridors
                    </div>
                    <div className="text-xl font-bold text-rose-400 font-mono mt-1">
                      {sc.critical_roads}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {/* Trade-Off Comparison Chart */}
        {chartData && (
          <div className="glass-card p-6 rounded-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
                  CLOSURE IMPACT COMPARISON CHART
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">Displaced Vehicles vs. Average Delay Increase</p>
              </div>
              <DataSourceBadge source="simulated" />
            </div>

            <div className="h-[300px] w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="closure" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: 'rgba(99,102,241,0.2)',
                      borderRadius: '12px',
                    }}
                  />
                  <Bar dataKey="displaced" name="Displaced Vehicles" fill="#6366f1" radius={[6, 6, 0, 0]} />
                  <Bar dataKey="delay" name="Avg Delay %" fill="#f59e0b" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
