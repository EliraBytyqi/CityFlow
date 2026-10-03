import React from 'react';
import { DataSourceBadge } from './DataSourceBadge';

interface HeaderProps {
  title?: string;
  subtitle?: string;
  dataSource?: string;
}

export const Header: React.FC<HeaderProps> = ({
  title = 'CITYFLOW AI',
  subtitle = 'See the impact before you change the street.',
  dataSource = 'demo',
}) => {
  return (
    <header className="h-16 px-8 border-b border-slate-800/80 bg-slate-950/40 backdrop-blur-md flex items-center justify-between sticky top-0 z-30">
      <div>
        <h1 className="text-base font-extrabold text-slate-100 tracking-tight">{title}</h1>
        <p className="text-xs text-slate-400 font-medium">{subtitle}</p>
      </div>

      <div className="flex items-center gap-3">
        <DataSourceBadge source={dataSource} />
        <div className="text-xs font-mono px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          MODEL ENGINE ONLINE
        </div>
      </div>
    </header>
  );
};
