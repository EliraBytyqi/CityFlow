import React, { useCallback, useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { DataSourceBadge } from '../components/DataSourceBadge';
import {
  getCameras, getCameraDetail, getCameraInference, startCameraInference,
  stopCameraInference, getCameraInferenceVideoUrl, type Camera, type CameraDetail, type CameraInference,
} from '../services/api';
import { Camera as CameraIcon, CheckCircle2, X } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export const Cameras: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [cameraDetail, setCameraDetail] = useState<CameraDetail | null>(null);
  const [inference, setInference] = useState<CameraInference | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getCameras().then(setCameras).catch((error) => setLoadError(error.message));
  }, []);

  const closeCamera = useCallback(() => {
    if (selectedCameraId) void stopCameraInference(selectedCameraId).catch(() => undefined);
    setSelectedCameraId(null);
    setCameraDetail(null);
    setInference(null);
  }, [selectedCameraId]);

  useEffect(() => () => {
    if (selectedCameraId) void stopCameraInference(selectedCameraId).catch(() => undefined);
  }, [selectedCameraId]);

  useEffect(() => {
    if (!selectedCameraId) return;
    const cameraId = selectedCameraId;
    let cancelled = false;
    setCameraDetail(null);
    setInference(null);
    setLoadError(null);
    Promise.all([getCameraDetail(cameraId), startCameraInference(cameraId)])
      .then(([detail, state]) => {
        if (!cancelled) {
          setCameraDetail(detail);
          setInference(state);
        }
      })
      .catch((error) => { if (!cancelled) setLoadError(error.message); });
    const poll = window.setInterval(() => {
      getCameraInference(cameraId).then((state) => { if (!cancelled) setInference(state); })
        .catch(() => undefined);
    }, 2000);
    return () => { cancelled = true; window.clearInterval(poll); };
  }, [selectedCameraId]);

  return (
    <div className="flex flex-col min-h-screen">
      <Header title="AI CAMERA MONITORS" subtitle="Live traffic video and vehicle detection from deployed cameras" />
      <main className="p-8 flex flex-col gap-6 flex-1 max-w-[1600px] w-full mx-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wide">LIVE VEHICLE DETECTION CAMERAS ({cameras.filter((camera) => camera.stream_url).length})</h2>
            <p className="text-xs text-slate-400">Select a camera to open its live feed and start YOLO vehicle predictions.</p>
          </div>
          <DataSourceBadge source="observed" />
        </div>
        {loadError && <p role="alert" className="text-sm text-rose-300">{loadError}</p>}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {cameras.filter((cam) => cam.stream_url).map((cam) => (
            <button key={cam.id} type="button" onClick={() => setSelectedCameraId(cam.id)}
              className={`glass-card text-left p-5 rounded-2xl flex flex-col gap-3 cursor-pointer border transition-all ${selectedCameraId === cam.id ? 'border-cyan-500/50 bg-cyan-950/20 shadow-lg shadow-cyan-500/10' : 'border-slate-800 hover:border-slate-700'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2"><div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"><CameraIcon className="w-4 h-4" /></div><span className="text-xs font-mono font-bold text-slate-300">{cam.id}</span></div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> {cam.stream_url ? 'READY' : 'NO FEED'}</span>
              </div>
              <div className="text-sm font-bold text-slate-100 mt-1">{cam.name}</div>
              <div className="text-xs text-slate-400">Live traffic camera</div>
              <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-slate-800/60 mt-1">
                <div><span className="text-slate-500 text-[10px] uppercase">Daily Flow</span><div className="font-mono font-bold text-slate-200">{cam.latest_count ? cam.latest_count.toLocaleString() : '---'}</div></div>
                <div><span className="text-slate-500 text-[10px] uppercase">Peak Hour</span><div className="font-mono font-bold text-cyan-400">{cam.peak_hour !== null ? `${cam.peak_hour.toString().padStart(2, '0')}:00` : '---'}</div></div>
              </div>
            </button>
          ))}
        </div>

        {selectedCameraId && (
          <section className="glass-card p-6 rounded-2xl border border-cyan-500/30 flex flex-col gap-4 animate-fade-in relative">
            <button type="button" aria-label="Close camera" onClick={closeCamera} className="absolute top-4 right-4 z-10 text-slate-400 hover:text-slate-100"><X className="w-5 h-5" /></button>
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 pr-8">
              <div className="flex items-center gap-3"><div className="p-2.5 rounded-xl bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"><CameraIcon className="w-5 h-5" /></div><div><h3 className="text-base font-bold text-slate-100">{cameraDetail?.name ?? 'Opening camera…'}</h3><p className="text-xs text-slate-400">Live location feed</p></div></div>
              <span className={`text-xs font-semibold ${inference?.status === 'live' ? 'text-emerald-400' : inference?.status === 'error' ? 'text-rose-400' : 'text-amber-300'}`}>MODEL {inference?.status?.toUpperCase() ?? 'STARTING'}</span>
            </div>
            {cameraDetail?.stream_url && <div className="overflow-hidden rounded-xl bg-black"><img key={selectedCameraId} src={getCameraInferenceVideoUrl(selectedCameraId)} alt={`Live video with vehicle detection boxes for ${cameraDetail.name}`} className="block w-full max-h-[65vh] object-contain" /><p className="px-3 py-2 text-xs text-slate-400">Live model output · detected vehicles are outlined and labeled on each frame</p></div>}
            {inference?.error && <p role="alert" className="text-sm text-rose-300">Prediction error: {inference.error}. Check that the backend has the YOLO dependencies and yolo11m.pt model file.</p>}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
              {[['Vehicles', inference?.total], ['Cars', inference?.counts.cars], ['Trucks', inference?.counts.trucks], ['Buses', inference?.counts.buses], ['Motorcycles', inference?.counts.motorcycles]].map(([label, value]) => <div key={String(label)} className="rounded-xl bg-slate-900/60 border border-slate-800 p-3"><div className="text-[10px] uppercase text-slate-500">{label}</div><div className="font-mono font-bold text-cyan-300">{value ?? '—'}</div></div>)}
            </div>
            {inference?.updated_at && <p className="text-[11px] text-slate-500">Latest prediction: {new Date(inference.updated_at).toLocaleTimeString()}</p>}
            {cameraDetail && <><DataSourceBadge source={cameraDetail.data_source} /><div className="h-[260px] w-full pt-2"><ResponsiveContainer width="100%" height="100%"><AreaChart data={cameraDetail.hourly_data.map((h) => ({ hourStr: `${h.hour.toString().padStart(2, '0')}:00`, ...h }))}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" /><XAxis dataKey="hourStr" stroke="#64748b" /><YAxis stroke="#64748b" /><Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: 'rgba(6,182,212,0.3)', borderRadius: '12px' }} /><Area type="monotone" dataKey="total" stroke="#06b6d4" fill="rgba(6,182,212,0.15)" strokeWidth={3} /></AreaChart></ResponsiveContainer></div></>}
          </section>
        )}
      </main>
    </div>
  );
};
