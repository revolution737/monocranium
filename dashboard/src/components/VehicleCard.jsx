import React from 'react';

export function VehicleCard({ vehicle, isActive, onClick }) {
  const isRover = vehicle.vehicle_type === 'rover';

  return (
    <div
      onClick={onClick}
      style={{
        padding: '12px',
        borderRadius: 'var(--radius)',
        backgroundColor: isActive ? 'var(--bg-tertiary)' : 'transparent',
        border: isActive ? '1px solid var(--accent-blue)' : '1px solid var(--border)',
        cursor: 'pointer',
        transition: 'all var(--transition)',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>{isRover ? '🚜' : '🛸'}</span>
          <span>SYSID #{vehicle.system_id}</span>
        </span>
        <span className={`badge ${isActive ? 'badge--blue' : 'badge--green'}`}>
          {vehicle.vehicle_type}
        </span>
      </div>
      <div style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
        <span>FW: {vehicle.firmware_version}</span>
        <span>{vehicle.autopilot_type}</span>
      </div>
    </div>
  );
}
