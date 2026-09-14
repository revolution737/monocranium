import React from 'react';
import { VehicleCard } from './VehicleCard';

export function Sidebar({
  currentPage,
  onNavigate,
  vehicles = [],
  activeSystemId,
  onSelectVehicle,
}) {
  const navItems = [
    { id: 'setup', label: 'Setup & Scan', icon: '⚙️' },
    { id: 'dashboard', label: 'Telemetry & Flight', icon: '📊' },
    { id: 'parameters', label: 'Parameters', icon: '📋' },
  ];

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div
        style={{
          padding: '20px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
        }}
      >
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: 'var(--radius)',
            backgroundColor: 'var(--accent-blue-bg)',
            border: '1px solid rgba(88, 166, 255, 0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '18px',
          }}
        >
          💀
        </div>
        <div>
          <h2 style={{ fontSize: '15px', fontWeight: 700, letterSpacing: '-0.02em' }}>MONOCRANIUM</h2>
          <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>MAVLink Bridge v0.1.0</span>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ padding: '16px 12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', padding: '0 8px 6px' }}>
          Navigation
        </span>
        {navItems.map((item) => {
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className="btn"
              style={{
                justifyContent: 'flex-start',
                backgroundColor: isActive ? 'var(--bg-tertiary)' : 'transparent',
                borderColor: isActive ? 'var(--border)' : 'transparent',
                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontWeight: isActive ? 600 : 500,
                padding: '8px 12px',
              }}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Vehicles List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px', borderTop: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 4px 10px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Connected Vehicles ({vehicles.length})
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {vehicles.map((v) => (
            <VehicleCard
              key={v.system_id}
              vehicle={v}
              isActive={v.system_id === activeSystemId}
              onClick={() => onSelectVehicle(v.system_id)}
            />
          ))}
          {vehicles.length === 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: '12px', textAlign: 'center', padding: '24px 12px' }}>
              No vehicles detected. Run scan in Setup.
            </div>
          )}
        </div>
      </div>

      {/* Footer Info */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', fontSize: '11px', color: 'var(--text-muted)' }}>
        <span>Target: 4WD Skid-Steer Rover</span>
      </div>
    </aside>
  );
}
