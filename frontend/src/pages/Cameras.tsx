import React, { useCallback, useEffect, useState } from 'react';
import { Header } from '../components/Header';
import {
  getCameras, getCameraDetail, getCameraInference, startCameraInference,
  stopCameraInference, getCameraInferenceVideoUrl, type Camera, type CameraDetail, type CameraInference,
} from '../services/api';
import { ArrowRight, Camera as CameraIcon, Check, CircleAlert, LoaderCircle, X } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

const stateCopy: Record<CameraInference['status'], string> = {
  stopped: 'Model stopped', connecting: 'Starting model', live: 'Inference running', error: 'Needs attention',
};

export const Cameras: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [cameraDetail, setCameraDetail] = useState<CameraDetail | null>(null);
  const [inference, setInference] = useState<CameraInference | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoadingCameras, setIsLoadingCameras] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getCameras().then((data) => { if (!cancelled) setCameras(data.filter((camera) => camera.stream_url)); })
      .catch((error: Error) => { if (!cancelled) setLoadError(error.message); })
      .finally(() => { if (!cancelled) setIsLoadingCameras(false); });
    return () => { cancelled = true; };
  }, []);

  const closeCamera = useCallback(() => {
    if (selectedCameraId) void stopCameraInference(selectedCameraId).catch(() => undefined);
    setSelectedCameraId(null); setCameraDetail(null); setInference(null); setLoadError(null);
  }, [selectedCameraId]);

  const selectCamera = (cameraId: string) => {
    if (cameraId === selectedCameraId) {
      setLoadError(null);
      startCameraInference(cameraId).then(setInference)
        .catch((error: Error) => setLoadError(error.message));
      return;
    }
    setCameraDetail(null); setInference(null); setLoadError(null);
    setSelectedCameraId(cameraId);
  };

  useEffect(() => () => {
    if (selectedCameraId) void stopCameraInference(selectedCameraId).catch(() => undefined);
  }, [selectedCameraId]);

  useEffect(() => {
    if (!selectedCameraId) return;
    const cameraId = selectedCameraId;
    let cancelled = false;
    Promise.all([getCameraDetail(cameraId), startCameraInference(cameraId)])
      .then(([detail, state]) => { if (!cancelled) { setCameraDetail(detail); setInference(state); } })
      .catch((error: Error) => { if (!cancelled) setLoadError(error.message); });
    const poll = window.setInterval(() => {
      getCameraInference(cameraId).then((state) => { if (!cancelled) setInference(state); })
        .catch((error: Error) => { if (!cancelled) setLoadError(error.message); });
    }, 1500);
    return () => { cancelled = true; window.clearInterval(poll); };
  }, [selectedCameraId]);

  const live = inference?.status === 'live';
  const hasError = inference?.status === 'error';

  return (
    <div className="page-view cameras-view">
      <Header title="Live camera desk" subtitle="Choose a location. The backend runs YOLO and returns annotated frames." dataSource={live ? 'observed' : 'demo'} />
      <main className="page-shell camera-page-shell">
        <section className="camera-intro">
          <div><div className="eyebrow">FIELD MONITORING <span className="camera-count">/ {cameras.length || '—'} LOCATIONS</span></div><h2>What’s moving<br /><em>on the ground?</em></h2><p>Open a feed to inspect live detections. Select another location at any time to switch the model.</p></div>
          <div className="camera-intro-mark"><span>YOLO</span><strong>ON</strong><small>ON DEMAND</small></div>
        </section>

        {loadError && !selectedCameraId && <div role="alert" className="notice notice-error"><CircleAlert size={16} /> Could not load camera locations: {loadError}</div>}

        <section className="camera-workspace">
          <div className="camera-selector panel">
            <div className="panel-heading"><div><div className="eyebrow">CAMERA LOCATIONS</div><h3>Choose a feed</h3></div><span className="selector-count">{cameras.length.toString().padStart(2, '0')} FEEDS</span></div>
            {isLoadingCameras ? <div className="camera-skeleton" aria-label="Loading camera feeds">{Array.from({ length: 4 }, (_, i) => <span className="skeleton-line" key={i} />)}</div>
              : cameras.length === 0 ? <div className="empty-state"><CameraIcon size={22} /><strong>No live camera feeds found</strong><span>Confirm the backend is running and camera stream URLs are configured.</span></div>
                : <div className="camera-choice-list">{cameras.map((camera, index) => (
                  <button key={camera.id} type="button" onClick={() => selectCamera(camera.id)} aria-pressed={selectedCameraId === camera.id}
                    className={`camera-choice ${selectedCameraId === camera.id ? 'selected' : ''}`}>
                    <span className="camera-index">{String(index + 1).padStart(2, '0')}</span>
                    <span className="camera-choice-icon"><CameraIcon size={17} /></span>
                    <span className="camera-choice-name">{camera.name}<small>{camera.id}</small></span>
                    <span className="configured-pill"><span /> READY</span>
                    <ArrowRight className="choice-arrow" size={15} />
                  </button>
                ))}</div>}
          </div>

          <section className="camera-viewer panel" aria-live="polite">
            {!selectedCameraId ? <div className="viewer-empty"><div className="viewer-empty-icon"><CameraIcon size={28} /></div><div className="eyebrow">LIVE MODEL OUTPUT</div><h3>Pick a camera to begin</h3><p>Your selected feed will appear here with vehicle boxes and class labels drawn by the model.</p><span className="viewer-hint">No camera is running yet</span></div> : <>
              <div className="viewer-header"><div className="viewer-title"><div className="eyebrow">{cameraDetail?.id ?? 'CONNECTING'} <span>/ LIVE FEED</span></div><h3>{cameraDetail?.name ?? 'Connecting to camera…'}</h3></div>
                <div className={`inference-state ${hasError ? 'failed' : live ? 'running' : ''}`}>
                  {hasError ? <CircleAlert size={14} /> : live ? <Check size={14} /> : <LoaderCircle size={14} className="spin" />}
                  {inference ? stateCopy[inference.status] : 'Starting model'}
                </div>
                <button type="button" onClick={closeCamera} aria-label="Close live camera" className="viewer-close"><X size={18} /></button>
              </div>
              <div className={`video-stage ${hasError ? 'video-failed' : ''}`}>
                {hasError ? <div className="video-message"><CircleAlert size={24} /><strong>We couldn’t read this stream</strong><span>{inference?.error}</span><small>Check the backend terminal for stream or model details, then select this location to retry.</small></div>
                  : cameraDetail ? <img key={selectedCameraId} src={getCameraInferenceVideoUrl(selectedCameraId)} alt={`Live ${cameraDetail.name} video with YOLO vehicle bounding boxes`} />
                    : <div className="video-message"><LoaderCircle className="spin" size={22} /><span>Connecting to stream and loading the model…</span></div>}
                {!hasError && live && <div className="frame-label"><span className="tiny-pulse" /> YOLO DETECTION OUTPUT</div>}
              </div>
              {loadError && <div role="alert" className="notice notice-error"><CircleAlert size={16} /> {loadError}</div>}
              <div className="detection-strip" aria-label="Current vehicle detections">
                {[['Vehicles', inference?.total], ['Cars', inference?.counts.cars], ['Trucks', inference?.counts.trucks], ['Buses', inference?.counts.buses], ['Motorcycles', inference?.counts.motorcycles]].map(([label, value]) => <div className="detection-metric" key={String(label)}><span>{label}</span><strong>{live ? value ?? 0 : '—'}</strong></div>)}
              </div>
              {inference?.updated_at && <p className="frame-time">Last inference frame · {new Date(inference.updated_at).toLocaleTimeString()}</p>}
              {cameraDetail && <div className="history-block"><div className="history-heading"><div><div className="eyebrow">VOLUME HISTORY</div><h4>{cameraDetail.data_source === 'demo' ? 'Sample hourly baseline' : cameraDetail.data_source === 'mixed' ? 'Baseline + live model counts' : 'Observed hourly counts'}</h4></div><span className={`history-source ${cameraDetail.data_source !== 'observed' ? 'sample' : ''}`}>{cameraDetail.data_source === 'demo' ? 'SAMPLE DATA' : cameraDetail.data_source === 'mixed' ? 'MIXED SOURCES' : 'OBSERVED'}</span></div>
                {cameraDetail.hourly_data.length ? <div className="history-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={cameraDetail.hourly_data.map((hour) => ({ ...hour, time: `${String(hour.hour).padStart(2, '0')}:00` }))} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}><CartesianGrid strokeDasharray="2 5" vertical={false} stroke="#e5e9e1" /><XAxis dataKey="time" tickLine={false} axisLine={false} stroke="#79857b" /><YAxis tickLine={false} axisLine={false} stroke="#79857b" /><Tooltip contentStyle={{ backgroundColor: '#fffefa', borderColor: '#dce3db', borderRadius: '8px', color: '#203027' }} /><Area type="monotone" dataKey="total" stroke="#39775d" fill="#dcebe0" strokeWidth={2} /></AreaChart></ResponsiveContainer></div> : <div className="history-empty">No hourly observations yet. Live frame detections will appear above.</div>}
              </div>}
            </>}
          </section>
        </section>
        <p className="camera-footnote">“Ready” means a stream URL is configured. The live status appears only after the model successfully returns its first annotated frame.</p>
      </main>
    </div>
  );
};
