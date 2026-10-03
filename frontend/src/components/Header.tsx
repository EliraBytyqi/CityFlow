import React from 'react';
import { DataSourceBadge } from './DataSourceBadge';

interface HeaderProps { title?: string; subtitle?: string; dataSource?: string; }

export const Header: React.FC<HeaderProps> = ({
  title = 'Overview', subtitle = 'A clear view of traffic, before the street changes.', dataSource = 'demo',
}) => (
  <header className="topbar">
    <div className="topbar-title">
      <div className="eyebrow">CITYFLOW <span>/</span> KOSOVO</div>
      <h1>{title}</h1>
      <p>{subtitle}</p>
    </div>
    <div className="topbar-meta"><span className="system-note">LOCAL WORKSPACE</span><DataSourceBadge source={dataSource} /></div>
  </header>
);
