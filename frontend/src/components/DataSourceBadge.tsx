import React from 'react';

interface DataSourceBadgeProps {
  source?: 'observed' | 'estimated' | 'simulated' | 'demo' | string;
  className?: string;
}

export const DataSourceBadge: React.FC<DataSourceBadgeProps> = ({ source = 'demo', className = '' }) => {
  const normalizedSource = source.toLowerCase();

  let label = 'DEMO DATA';
  let badgeClass = 'badge-demo';

  if (normalizedSource === 'observed') {
    label = 'OBSERVED';
    badgeClass = 'badge-observed';
  } else if (normalizedSource === 'estimated') {
    label = 'ESTIMATED';
    badgeClass = 'badge-estimated';
  } else if (normalizedSource === 'simulated') {
    label = 'SIMULATED';
    badgeClass = 'badge-simulated';
  } else if (normalizedSource === 'demo') {
    label = 'DEMO DATA';
    badgeClass = 'badge-demo';
  } else if (normalizedSource === 'mixed') {
    label = 'MIXED SOURCES';
    badgeClass = 'badge-mixed';
  }

  return (
    <span className={`badge ${badgeClass} ${className}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80 animate-pulse" />
      {label}
    </span>
  );
};
