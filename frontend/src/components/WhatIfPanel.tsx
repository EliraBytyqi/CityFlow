import React, { useState } from 'react';
import { ArrowRight, Clock3, Route, TriangleAlert } from 'lucide-react';
import { type Road } from '../services/api';

interface WhatIfPanelProps {
  selectedRoad: Road | null;
  onSimulate: (roadId: string, closurePercentage: number, hour: number) => void;
  isSimulating: boolean;
  onClosurePreview: (roadId: string, closurePercentage: number) => void;
}

export const WhatIfPanel: React.FC<WhatIfPanelProps> = ({ selectedRoad, onSimulate, isSimulating, onClosurePreview }) => {
  const [closurePct, setClosurePct] = useState(100);
  const [selectedHour, setSelectedHour] = useState(8);
  const hours = [6, 8, 10, 12, 14, 16, 18, 20];

  return (
    <section className="planner-panel command-planner">
      <div className="planner-title"><span className="planner-icon"><Route size={18} /></span><div><div className="eyebrow">NETWORK SCENARIO</div><h2>Close a road</h2></div></div>

      <div className="selected-link"><div className="selected-link-head"><span>SELECTED LINK</span><code>{selectedRoad?.id ?? '—'}</code></div><strong>{selectedRoad?.name ?? 'Loading road network…'}</strong><div className="selected-link-flow">Baseline flow <b>{selectedRoad ? `${selectedRoad.current_flow.toLocaleString()} veh/day` : '—'}</b></div></div>

      <fieldset className="planner-fieldset closure-slider-field"><legend>CLOSURE EXTENT <strong className="selected-hour">{closurePct}%</strong></legend><input aria-label="Closure extent" className="closure-slider" type="range" min="25" max="100" step="25" value={closurePct} onChange={(event) => { const percentage = Number(event.target.value); setClosurePct(percentage); if (selectedRoad) onClosurePreview(selectedRoad.id, percentage); }} /><div className="slider-scale"><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div></fieldset>

      <fieldset className="planner-fieldset"><legend><Clock3 size={13} /> SIMULATION HOUR <strong className="selected-hour">{String(selectedHour).padStart(2, '0')}:00</strong></legend><div className="choice-grid hour-grid">{hours.map((hour) => <button key={hour} type="button" aria-pressed={selectedHour === hour} onClick={() => setSelectedHour(hour)} className={`choice-button ${selectedHour === hour ? 'active' : ''}`}>{String(hour).padStart(2, '0')}</button>)}</div></fieldset>

      <button type="button" className="planner-submit" disabled={!selectedRoad || isSimulating} onClick={() => selectedRoad && onSimulate(selectedRoad.id, closurePct, selectedHour)}>
        {isSimulating ? <><span className="button-spinner" /> SIMULATING NETWORK…</> : <>SIMULATE <ArrowRight size={16} /> </>}
      </button>
      {!selectedRoad && <div className="planner-inline-note"><TriangleAlert size={14} /> Road network is loading or unavailable.</div>}
    </section>
  );
};
