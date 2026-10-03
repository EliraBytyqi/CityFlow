import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { DataSourceBadge } from '../components/DataSourceBadge';
import {
  getTrafficTimeline,
  getRoads,
  type TrafficTimeline,
  type Road,
} from '../services/api';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from 'recharts';
import { Clock, Truck, Bus, Car } from 'lucide-react';

export const TrafficAnalytics: React.FC = () => {
  const [timeline, setTimeline] = useState<TrafficTimeline | null>(null);
  const [roads, setRoads] = useState<Road[]>([]);
  const [activeFilter, setActiveFilter] = useState<'total' | 'cars' | 'trucks' | 'buses' | 'motorcycles'>('total');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [tl, rData] = await Promise.all([
          getTrafficTimeline(),
          getRoads(),
        ]);
        setTimeline(tl);
        setRoads(rData);
      } catch (err) {
        console.error('Failed to load analytics data:', err);
      }
    };
    fetchData();
  }, []);

  if (!timeline) {
    return (
      <div className="flex flex-col min-h-screen">
        <Header title="TRAFFIC ANALYTICS" subtitle="24-Hour Traffic Observation & Breakdown" />
        <div className="flex-1 flex items-center justify-center">
          <div className="loading-spinner" />
        </div>
      </div>
    );
  }

  // Find peak hour automatically
  const peakPoint = timeline.data.reduce(
    (max, p) => (p.total > max.total ? p : max),
    timeline.data[0] || { hour: 8, total: 0 }
  );

  // Total composition totals across 24h
  const totalCars = timeline.data.reduce((sum, p) => sum + p.cars, 0);
  const totalTrucks = timeline.data.reduce((sum, p) => sum + p.trucks, 0);
  const totalBuses = timeline.data.reduce((sum, p) => sum + p.buses, 0);
  const totalMotos = timeline.data.reduce((sum, p) => sum + p.motorcycles, 0);
  const grandTotal = totalCars + totalTrucks + totalBuses + totalMotos || 1;

  const formattedChartData = timeline.data.map((p) => ({
    hourStr: `${p.hour.toString().padStart(2, '0')}:00`,
    ...p,
  }));

  const getFilterColor = () => {
    switch (activeFilter) {
      case 'cars': return '#6366f1';
      case 'trucks': return '#f59e0b';
      case 'buses': return '#06b6d4';
      case 'motorcycles': return '#ec4899';
      default: return '#8b5cf6';
    }
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        title="TRAFFIC ANALYTICS"
        subtitle="24-Hour Traffic Volume & Vehicle Composition"
        dataSource={timeline.data_source}
      />

      <main className="p-8 flex flex-col gap-6 flex-1 max-w-[1600px] w-full mx-auto">
        {/* Peak Hour & Composition Highlight Banner */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="glass-card p-5 rounded-2xl border border-indigo-500/20 bg-indigo-950/20">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-400 uppercase">
              <Clock className="w-4 h-4 text-indigo-400" />
              Peak Traffic Hour
            </div>
            <div className="text-3xl font-extrabold text-indigo-300 font-mono mt-1">
              {peakPoint.hour.toString().padStart(2, '0')}:00
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Peak Volume: <span className="font-bold text-slate-200">{peakPoint.total.toLocaleString()} veh/hr</span>
            </div>
          </div>

          <div className="glass-card p-5 rounded-2xl">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase flex items-center gap-1.5">
                <Car className="w-4 h-4 text-indigo-400" /> Passenger Cars
              </span>
              <span className="text-xs font-mono font-bold text-indigo-400">
                {Math.round((totalCars / grandTotal) * 100)}%
              </span>
            </div>
            <div className="text-2xl font-extrabold text-slate-100 font-mono mt-1">
              {totalCars.toLocaleString()}
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
              <div className="bg-indigo-500 h-full" style={{ width: `${(totalCars / grandTotal) * 100}%` }} />
            </div>
          </div>

          <div className="glass-card p-5 rounded-2xl">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase flex items-center gap-1.5">
                <Truck className="w-4 h-4 text-amber-400" /> Freight Trucks
              </span>
              <span className="text-xs font-mono font-bold text-amber-400">
                {Math.round((totalTrucks / grandTotal) * 100)}%
              </span>
            </div>
            <div className="text-2xl font-extrabold text-slate-100 font-mono mt-1">
              {totalTrucks.toLocaleString()}
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
              <div className="bg-amber-500 h-full" style={{ width: `${(totalTrucks / grandTotal) * 100}%` }} />
            </div>
          </div>

          <div className="glass-card p-5 rounded-2xl">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase flex items-center gap-1.5">
                <Bus className="w-4 h-4 text-cyan-400" /> Transit Buses
              </span>
              <span className="text-xs font-mono font-bold text-cyan-400">
                {Math.round((totalBuses / grandTotal) * 100)}%
              </span>
            </div>
            <div className="text-2xl font-extrabold text-slate-100 font-mono mt-1">
              {totalBuses.toLocaleString()}
            </div>
            <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
              <div className="bg-cyan-500 h-full" style={{ width: `${(totalBuses / grandTotal) * 100}%` }} />
            </div>
          </div>
        </div>

        {/* 24-Hour Main Chart */}
        <div className="glass-card p-6 rounded-2xl flex flex-col gap-4">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-slate-100 uppercase tracking-wide">
                  TRAFFIC VOLUME — 24 HOURS
                </h3>
                <DataSourceBadge source={timeline.data_source} />
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Hourly vehicle count aggregated across all active AI monitoring points
              </p>
            </div>

            {/* Filter Toggle Buttons */}
            <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
              {(['total', 'cars', 'trucks', 'buses', 'motorcycles'] as const).map((filter) => (
                <button
                  key={filter}
                  type="button"
                  onClick={() => setActiveFilter(filter)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase transition-all ${
                    activeFilter === filter
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {filter}
                </button>
              ))}
            </div>
          </div>

          {/* Recharts Area Chart */}
          <div className="h-[360px] w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={formattedChartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="trafficGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={getFilterColor()} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={getFilterColor()} stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="hourStr" tickLine={false} stroke="#64748b" />
                <YAxis tickLine={false} stroke="#64748b" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: 'rgba(99,102,241,0.2)',
                    borderRadius: '12px',
                    color: '#f8fafc',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey={activeFilter}
                  stroke={getFilterColor()}
                  strokeWidth={3}
                  fillOpacity={1}
                  fill="url(#trafficGradient)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Traffic by Road & Composition Breakdown Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Traffic by Road */}
          <div className="glass-card p-6 rounded-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
                TRAFFIC BY ROAD (DAILY VOLUME)
              </h3>
              <span className="text-xs text-slate-400">{roads.length} Monitored Corridors</span>
            </div>

            <div className="flex flex-col gap-3 max-h-[320px] overflow-y-auto pr-1">
              {roads.map((road) => (
                <div key={road.id} className="flex flex-col gap-1 p-3 rounded-xl bg-slate-800/30 border border-slate-700/30">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                    <span>{road.name}</span>
                    <span className="font-mono text-indigo-300">{road.current_flow.toLocaleString()} veh/day</span>
                  </div>
                  <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full rounded-full"
                      style={{ width: `${Math.min((road.current_flow / road.capacity) * 100, 100)}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-slate-500 pt-0.5">
                    <span>Capacity: {road.capacity.toLocaleString()}</span>
                    <span>{Math.round((road.current_flow / road.capacity) * 100)}% Utilization</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Traffic Composition Breakdown */}
          <div className="glass-card p-6 rounded-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wide">
                VEHICLE CLASSIFICATION BREAKDOWN
              </h3>
              <span className="text-xs text-slate-400">AI Detection Distribution</span>
            </div>

            <div className="h-[280px] w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={formattedChartData.slice(7, 20)}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="hourStr" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: 'rgba(99,102,241,0.2)',
                      borderRadius: '12px',
                    }}
                  />
                  <Legend />
                  <Bar dataKey="cars" name="Cars" stackId="a" fill="#6366f1" />
                  <Bar dataKey="trucks" name="Trucks" stackId="a" fill="#f59e0b" />
                  <Bar dataKey="buses" name="Buses" stackId="a" fill="#06b6d4" />
                  <Bar dataKey="motorcycles" name="Motorcycles" stackId="a" fill="#ec4899" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};
