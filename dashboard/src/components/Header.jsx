import React, { useState, useEffect } from 'react';
import { ConnectionBadge } from './ConnectionBadge';

export function Header({ title, isConnected, activeVehicle }) {
  const [timeStr, setTimeStr] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeStr(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="header">
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <h1 style={{ fontSize: '16px', fontWeight: 600 }}>{title}</h1>
        {activeVehicle && (
          <span className="badge badge--blue">
            Active: SYSID #{activeVehicle.system_id} ({activeVehicle.vehicle_type})
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <ConnectionBadge isConnected={isConnected} />
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-tertiary)',
            padding: '4px 8px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border)',
          }}
        >
          {timeStr}
        </span>
      </div>
    </header>
  );
}
