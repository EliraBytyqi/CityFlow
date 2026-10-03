import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { TrafficAnalytics } from './pages/TrafficAnalytics';
import { Scenarios } from './pages/Scenarios';
import { Cameras } from './pages/Cameras';
import { type SimulationResult } from './services/api';

export const AppContent: React.FC = () => {
  const navigate = useNavigate();
  const [simulationResult, setSimulationResult] = useState<SimulationResult | null>(null);
  return (
    <div className="app-layout">
      <Sidebar onOpenCameras={() => navigate('/cameras')} />

      <div className="main-content">
        <Routes>
          <Route
            path="/"
            element={
              <Dashboard
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
