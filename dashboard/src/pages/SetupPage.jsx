import React, { useState } from 'react';

export function SetupPage({
  vehicles = [],
  activeVehicle,
  onRunAutoConfig,
  connectionStatus = [],
}) {
  const [host, setHost] = useState('127.0.0.1');
  const [port, setPort] = useState(5770);
  const [protocol, setProtocol] = useState('tcp');
  const [isScanning, setIsScanning] = useState(false);

  const handleScan = async () => {
    setIsScanning(true);
    await onRunAutoConfig([{ address: host, port: parseInt(port, 10), protocol }]);
    setTimeout(() => setIsScanning(false), 1500);
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Overview & Quick Scan */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Autonomous Vehicle Discovery & Calibration</span>
        </div>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', lineHeight: 1.6 }}>
          Monocranium bridges unmanned vehicle autopilots to Raspberry Pi and browser dashboards without requiring
          manual parameter calibration. Configure communication endpoints below to initiate MAVLink handshake and
          parameter synchronization.
        </p>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Host Address
            </label>
            <input
              type="text"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              className="input"
              placeholder="127.0.0.1"
            />
          </div>

          <div style={{ width: '120px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              TCP Port
            </label>
            <input
              type="number"
              value={port}
              onChange={(e) => setPort(e.target.value)}
              className="input"
              placeholder="5770"
            />
          </div>

          <div style={{ width: '120px' }}>
            <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Protocol
            </label>
            <select
              value={protocol}
              onChange={(e) => setProtocol(e.target.value)}
              className="input"
              style={{ cursor: 'pointer' }}
            >
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
            </select>
          </div>

          <button
            onClick={handleScan}
            disabled={isScanning}
            className="btn btn--primary"
            style={{ height: '36px', minWidth: '160px' }}
          >
            {isScanning ? 'Scanning...' : '🚀 Scan Endpoint'}
          </button>
        </div>
      </div>

      {/* Auto-Configuration Status Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
        {/* Discovered Vehicle Diagnostics */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Handshake Status</span>
            {activeVehicle ? (
              <span className="badge badge--green">Connected</span>
            ) : (
              <span className="badge badge--orange">Waiting</span>
            )}
          </div>

          {activeVehicle ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>System ID</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>#{activeVehicle.system_id}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Vehicle Type</span>
                <span style={{ textTransform: 'capitalize' }}>{activeVehicle.vehicle_type}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Autopilot Engine</span>
                <span style={{ textTransform: 'capitalize' }}>{activeVehicle.autopilot_type}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Firmware Version</span>
                <span style={{ fontFamily: 'var(--font-mono)' }}>v{activeVehicle.firmware_version}</span>
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '24px 0' }}>
              No active vehicle handshake. Ensure virtual rover simulator is running on port {port}.
            </div>
          )}
        </div>

        {/* Calibration Checklist */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Automatic Calibration Checklist</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span>{activeVehicle ? '✅' : '⏳'}</span>
              <div>
                <span style={{ fontWeight: 600, display: 'block' }}>1. MAVLink Protocol Handshake</span>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  HEARTBEAT message receipt and system identification
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span>{activeVehicle ? '✅' : '⏳'}</span>
              <div>
                <span style={{ fontWeight: 600, display: 'block' }}>2. Parameter Stream Synchronization</span>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Automatic query of rover physical dimensions, motor RPM, LiPo cell count
                </span>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span>{activeVehicle ? '✅' : '⏳'}</span>
              <div>
                <span style={{ fontWeight: 600, display: 'block' }}>3. Actuator Control Mapping</span>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  RC channel 1 (Steering) and channel 3 (Throttle) override active
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
