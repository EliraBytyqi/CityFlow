import React from 'react';
import { GitBranch } from 'lucide-react';
import { DataSourceBadge } from './DataSourceBadge';

interface AIExplanationCardProps {
  explanation: string | null;
}

export const AIExplanationCard: React.FC<AIExplanationCardProps> = ({ explanation }) => {
  if (!explanation) return null;

  return (
    <div className="glass-card p-5 rounded-xl animate-fade-in">
      <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <GitBranch className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              Modeled impact summary
            </h4>
            <p className="text-[11px] text-slate-400">Generated from the sample network simulation output</p>
          </div>
        </div>
        <DataSourceBadge source="simulated" />
      </div>

      <div className="flex items-start gap-3 pt-1">
        <div className="p-1.5 rounded-lg bg-slate-800/80 text-emerald-400 border border-slate-700/50 mt-0.5 shrink-0">
          <GitBranch className="w-4 h-4" />
        </div>
        <div className="text-xs text-slate-300 leading-relaxed font-normal">
          {explanation}
        </div>
      </div>
    </div>
  );
};
