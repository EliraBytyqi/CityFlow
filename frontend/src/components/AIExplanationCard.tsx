import React from 'react';
import { Sparkles, Bot } from 'lucide-react';
import { DataSourceBadge } from './DataSourceBadge';

interface AIExplanationCardProps {
  explanation: string | null;
}

export const AIExplanationCard: React.FC<AIExplanationCardProps> = ({ explanation }) => {
  if (!explanation) return null;

  return (
    <div className="glass-card p-5 rounded-2xl border border-purple-500/30 bg-gradient-to-r from-purple-950/20 via-slate-900/40 to-indigo-950/20 backdrop-blur-xl animate-fade-in shadow-xl">
      <div className="flex items-center justify-between mb-3 border-b border-purple-500/20 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              AI NETWORK IMPACT ANALYSIS
            </h4>
            <p className="text-[11px] text-slate-400">Natural-language synthesis derived strictly from simulation models</p>
          </div>
        </div>
        <DataSourceBadge source="simulated" />
      </div>

      <div className="flex items-start gap-3 pt-1">
        <div className="p-1.5 rounded-lg bg-slate-800/80 text-purple-400 border border-slate-700/50 mt-0.5 shrink-0">
          <Bot className="w-4 h-4" />
        </div>
        <div className="text-xs text-slate-300 leading-relaxed font-normal">
          {explanation}
        </div>
      </div>
    </div>
  );
};
