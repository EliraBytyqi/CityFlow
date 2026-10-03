import React, { useState, useEffect } from 'react';
import { Header } from '../components/Header';
import { DataSourceBadge } from '../components/DataSourceBadge';
import { getCameras, getCameraDetail, type Camera, type CameraDetail } from '../services/api';
import { Camera as CameraIcon, CheckCircle2, X } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const Cameras: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [cameraDetail, setCameraDetail] = useState<CameraDetail | null>(null);

  useEffect(() => {
    getCameras().then((cData) => setCameras(cData));
  }, []);

  const handleSelectCamera = (id: string) => {
    setSelectedCameraId(id);
    getCameraDetail(id)
      .then((detail) => setCameraDetail(detail))
      .catch((err) => console.error('Failed to load camera detail:', err));
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Header
        title="AI CAMERA MONITORS"
        subtitle="Real-time vehicle detection feeds from deployed vision edge nodes"
      />

      <main className="p-8 flex flex-col gap-6 flex-1 max-w-[1600px] w-full mx-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">
              DEPLOYED VEHICLE DETECTION CAMERAS ({cameras.length})
            </h2>
            <p className="text-xs text-slate-400">
              Receives vehicle counts directly from our existing AI computer vision model
            </p>
          </div>
          <DataSourceBadge source="observed" />
        </div>

        {/* Camera Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {cameras.map((cam) => (
            <div
              key={cam.id}
              onClick={() => handleSelectCamera(cam.id)}
              className={`glass-card p-5 rounded-2xl flex flex-col gap-3 cursor-pointer border transition-all ${
                selectedCameraId === cam.id
                  ? 'border-cyan-500/50 bg-cyan-950/20 shadow-lg shadow-cyan-500/10'
                  : 'border-slate-800 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                    <CameraIcon className="w-4 h-4" />
                  </div>
                  <span className="text-xs font-mono font-bold text-slate-300">{cam.id}</span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> ONLINE
                </span>
              </div>

              <div className="text-sm font-bold text-slate-100 mt-1">{cam.name}</div>
              <div className="text-xs text-slate-400">Road: {cam.road_name || 'N/A'}</div>

              <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-800/60 mt-1">
                <div>
                  <span className="text-slate-500 text-[10px] uppercase">Daily Flow</span>
                  <div className="font-mono font-bold text-slate-200">
                    {cam.latest_count ? cam.latest_count.toLocaleString() : '---'}
                  </div>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] uppercase">Peak Hour</span>
                  <div className="font-mono font-bold text-cyan-400">
                    {cam.peak_hour !== null ? `${cam.peak_hour.toString().padStart(2, '0')}:00` : '---'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Selected Camera Inspector Drawer / Modal */}
        {selectedCameraId && cameraDetail && (
          <div className="glass-card p-6 rounded-2xl border border-cyan-500/30 flex flex-col gap-4 animate-fade-in relative">
            <button
              type="button"
              onClick={() => {
                setSelectedCameraId(null);
                setCameraDetail(null);
              }}
              className="absolute top-4 right-4 text-slate-500 hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
                  <CameraIcon className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-100">{cameraDetail.name}</h3>
                  <p className="text-xs text-slate-400">
                    Associated Road: <span className="text-slate-200 font-semibold">{cameraDetail.road_name}</span>
                  </p>
                </div>
              </div>
              <DataSourceBadge source={cameraDetail.data_source} />
            </div>

            {/* 24-Hour Camera Chart */}
            <div className="h-[260px] w-full pt-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                  data={cameraDetail.hourly_data.map((h) => ({
                    hourStr: `${h.hour.toString().padStart(2, '0')}:00`,
                    ...h,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="hourStr" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: 'rgba(6,182,212,0.3)',
                      borderRadius: '12px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="total"
                    stroke="#06b6d4"
                    fill="rgba(6,182,212,0.15)"
                    strokeWidth={3}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};
