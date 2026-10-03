import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { TrafficAnalytics } from './pages/TrafficAnalytics';
import { Scenarios } from './pages/Scenarios';
import { Cameras } from './pages/Cameras';
import { type SimulationResult, runSimulation } from './services/api';
import { Sparkles } from 'lucide-react';

export const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const [selectedRoadId, setSelectedRoadId] = useState<string | null>('road_01');
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);
  const [isDemoRunning, setIsDemoRunning] = useState<boolean>(false);
  const [demoStep, setDemoStep] = useState<string>('');

  const runAutomatedDemo = async () => {
    setIsDemoRunning(true);

    const steps = [
      { text: '1/8 Loading City Network & AI Edge Cameras...', path: '/', delay: 2500, action: () => setSelectedRoadId(null) },
      { text: '2/8 Inspecting AI Camera Observations...', path: '/cameras', delay: 3500, action: () => {} },
      { text: '3/8 Analyzing 24-Hour Traffic Patterns...', path: '/analytics', delay: 3500, action: () => {} },
      { text: '4/8 Selecting Target Street: Weststraat...', path: '/', delay: 2500, action: () => setSelectedRoadId('road_01') },
      { text: '5/8 Executing 100% Closure Simulation...', path: '/', delay: 2000, action: () => {} },
    ];

    for (const step of steps) {
      setDemoStep(step.text);
      navigate(step.path);
      step.action();
      await new Promise((r) => setTimeout(r, step.delay));
    }

    // Run actual 100% simulation for Weststraat
    setDemoStep('6/8 Redistributing Displaced Traffic on Map...');
    try {
      const res = await runSimulation('road_01', 100, 8);
      setSimulationResult(res);
    } catch (e) {
      console.error(e);
    }
    await new Promise((r) => setTimeout(r, 4000));

    // Compare scenarios
    setDemoStep('7/8 Comparing 25% / 50% / 75% / 100% Closure Scenarios...');
    navigate('/scenarios');
    await new Promise((r) => setTimeout(r, 4000));

    // Return to dashboard with results & AI explanation
    setDemoStep('8/8 AI Impact Synthesis Generated. Demo Complete!');
    navigate('/');
    await new Promise((r) => setTimeout(r, 3000));

    setIsDemoRunning(false);
    setDemoStep('');
  };

  return (
    <div className="app-layout">
      <Sidebar onRunDemo={runAutomatedDemo} isDemoRunning={isDemoRunning} />

      {/* Demo Banner Overlay */}
      {isDemoRunning && (
        <div className="fixed top-3 right-8 z-[2000] glass-card px-5 py-3 rounded-2xl border border-pink-500/40 bg-slate-900/90 text-slate-100 flex items-center gap-3 shadow-2xl animate-pulse">
          <Sparkles className="w-5 h-5 text-pink-400" />
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-pink-400">
              AUTOMATED HACKATHON DEMO
            </div>
            <div className="text-xs font-semibold">{demoStep}</div>
          </div>
        </div>
      )}

      <div className="main-content">
        <Routes>
          <Route
            path="/"
            element={
              <Dashboard
                selectedRoadId={selectedRoadId}
                setSelectedRoadId={setSelectedRoadId}
                simulationResult={simulationResult}
                setSimulationResult={setSimulationResult}
              />
            }
          />
          <Route path="/analytics" element={<TrafficAnalytics />} />
          <Route path="/scenarios" element={<Scenarios />} />
          <Route path="/cameras" element={<Cameras />} />
        </Routes>
      </div>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;
