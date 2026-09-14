import React from 'react';

export function ConnectionBadge({ isConnected, label }) {
  const status = isConnected ? 'CONNECTED' : 'DISCONNECTED';
  const displayLabel = label || status;
  const badgeClass = isConnected ? 'badge--green' : 'badge--red';

  return (
    <span className={`badge ${badgeClass} animate-fade-in`}>
      <span className="badge-dot" style={{ animation: isConnected ? 'pulse 2s infinite' : 'none' }} />
      <span>{displayLabel}</span>
    </span>
  );
}
