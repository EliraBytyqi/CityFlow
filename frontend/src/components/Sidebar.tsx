import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, BarChart3, GitCompare, Camera, ArrowUpRight, Activity } from 'lucide-react';

interface SidebarProps { onOpenCameras?: () => void; }

const links = [
  { to: '/', label: 'Map', icon: LayoutDashboard, end: true },
  { to: '/analytics', label: 'Analyze', icon: BarChart3 },
  { to: '/scenarios', label: 'Scenarios', icon: GitCompare },
];

export const Sidebar: React.FC<SidebarProps> = ({ onOpenCameras }) => (
  <aside className="sidebar" aria-label="Main navigation">
    <NavLink to="/" className="brand-lockup" aria-label="CityFlow home">
      <span className="brand-mark"><Activity size={19} strokeWidth={2.4} /></span>
      <span className="logo-text"><strong>CITYFLOW</strong><small>KOSOVO OBSERVATORY</small></span>
    </NavLink>
    <nav className="side-nav">
      {links.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
          <Icon size={18} strokeWidth={1.8} /><span className="nav-text">{label}</span>
        </NavLink>
      ))}
    </nav>
    <div className="sidebar-foot">
      <button type="button" onClick={onOpenCameras} className="sidebar-cta" aria-label="Open live cameras" title="Open live cameras">
        <Camera size={16} /><span className="nav-text">Cameras</span><ArrowUpRight size={15} className="nav-text" />
      </button>
      <span className="sidebar-version">URBAN WHAT-IF ENGINE</span>
    </div>
  </aside>
);
