import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, BarChart3, GitCompare, Camera, Play, Activity } from 'lucide-react';

interface SidebarProps {
  onRunDemo?: () => void;
  isDemoRunning?: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ onRunDemo, isDemoRunning }) => {
  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30 shrink-0">
          <Activity className="w-5 h-5 text-white" />
        </div>
        <div className="logo-text">
          <div className="text-base font-black text-slate-100 tracking-wider">CITYFLOW AI</div>
          <div className="text-[10px] font-medium text-slate-400">Decision Support Platform</div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 py-4 flex flex-col gap-1">
        <NavLink
          to="/"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <LayoutDashboard className="w-4 h-4 shrink-0" />
          <span className="nav-text">Dashboard</span>
        </NavLink>

        <NavLink
          to="/analytics"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <BarChart3 className="w-4 h-4 shrink-0" />
          <span className="nav-text">Traffic Analytics</span>
        </NavLink>

        <NavLink
          to="/scenarios"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <GitCompare className="w-4 h-4 shrink-0" />
          <span className="nav-text">Scenarios</span>
        </NavLink>

        <NavLink
          to="/cameras"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <Camera className="w-4 h-4 shrink-0" />
          <span className="nav-text">Cameras</span>
        </NavLink>
      </nav>

      {/* Hackathon Demo Button */}
      <div className="p-4 border-t border-slate-800">
        <button
          type="button"
          onClick={onRunDemo}
          disabled={isDemoRunning}
          className="w-full py-3 px-4 rounded-xl bg-gradient-to-r from-pink-600 via-purple-600 to-indigo-600 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-lg shadow-pink-500/20 hover:opacity-95 transition-all disabled:opacity-50"
        >
          <Play className="w-4 h-4 fill-current" />
          <span>{isDemoRunning ? 'DEMO RUNNING...' : 'RUN HACKATHON DEMO'}</span>
        </button>
      </div>
    </aside>
  );
};
