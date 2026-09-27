import React, { useState } from 'react';
import { TelemetryGauge } from '../components/TelemetryGauge';
import { LogConsole } from '../components/LogConsole';

export function DashboardPage({
  telemetry,
  logs,
  onSendRcOverride,
  activeVehicle,
  onArmVehicle,
  onSetFlightMode,
}) {
  const isCopter = activeVehicle?.vehicle_type === 'copter';

  const [throttle, setThrottle] = useState(1500);
  const [steering, setSteering] = useState(1500);
  const [roll, setRoll] = useState(1500);
  const [pitch, setPitch] = useState(1500);
  const [yaw, setYaw] = useState(1500);
  const [isArmed, setIsArmed] = useState(false);
  const [flightMode, setFlightMode] = useState('STABILIZE');

  const handleThrottleChange = (val) => {
    const num = parseInt(val, 10);
    setThrottle(num);
    if (isCopter) {
      onSendRcOverride(num, roll, pitch, yaw, roll);
    } else {
      onSendRcOverride(num, steering);
    }
  };

  const handleSteeringChange = (val) => {
    const num = parseInt(val, 10);
    setSteering(num);
    onSendRcOverride(throttle, num);
  };

  const handleCopterAxis = (axis, val) => {
    const num = parseInt(val, 10);
    let r = roll;
    let p = pitch;
    let t = throttle;
    let y = yaw;
    if (axis === 'roll') { r = num; setRoll(num); }
    if (axis === 'pitch') { p = num; setPitch(num); }
    if (axis === 'yaw') { y = num; setYaw(num); }
    onSendRcOverride(t, r, p, y, r);
  };

  const centerSticks = () => {
    setRoll(1500);
    setPitch(1500);
    setThrottle(1500);
    setYaw(1500);
    onSendRcOverride(1500, 1500, 1500, 1500, 1500);
  };

  const drive = (thr, str) => {
    setThrottle(thr);
    setSteering(str);
    onSendRcOverride(thr, str);
  };

  const stop = () => drive(1500, 1500);

  const handleArmToggle = () => {
    const nextArmed = !isArmed;
    setIsArmed(nextArmed);
    onArmVehicle(nextArmed);
  };

  const handleModeChange = (e) => {
    const mode = e.target.value;
    setFlightMode(mode);
    onSetFlightMode(mode);
  };

  const yawDeg = ((telemetry.attitude.yaw * 180) / Math.PI).toFixed(1);
  const rollDeg = ((telemetry.attitude.roll * 180) / Math.PI).toFixed(1);
  const pitchDeg = ((telemetry.attitude.pitch * 180) / Math.PI).toFixed(1);

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Telemetry Metric Cards Grid */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px' }}>
        <TelemetryGauge
          title="Heading (Yaw)"
          value={`${yawDeg}°`}
          history={telemetry.history}
          dataKey="yaw"
          color="#58a6ff"
        />
        <TelemetryGauge
          title="Speed"
          value={telemetry.speed?.toFixed(2) || '0.00'}
          unit="m/s"
          history={telemetry.history}
          dataKey="speed"
          color="#3fb950"
        />
        <TelemetryGauge
          title="Battery Voltage"
          value={telemetry.battery.voltage?.toFixed(2) || '11.1'}
          unit="V"
          color="#d29922"
        />
        <TelemetryGauge
          title="Battery Current"
          value={telemetry.battery.current?.toFixed(2) || '0.0'}
          unit="A"
          color="#f85149"
        />
        <TelemetryGauge
          title="Battery Remaining"
          value={telemetry.battery.remaining}
          unit="%"
          color="#3fb950"
        />
        <TelemetryGauge
          title="GPS Satellites"
          value={telemetry.gps.satellites}
          unit="3D Fix"
          color="#58a6ff"
        />
      </div>

      {/* Control & Attitude Details */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        {/* Interactive RC Actuator Control Pad */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">🎮 MAVLink RC Actuator Override</span>
            <span className={`badge ${isCopter ? 'badge--green' : 'badge--blue'}`}>
              {isCopter ? '4-Axis Flight Controller' : 'Skid-Steer Control'}
            </span>
          </div>

          {isCopter ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Throttle (CH3) */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Throttle / Altitude (CH3)</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{throttle} µs</span>
                </div>
                <input
                  type="range"
                  min="1000"
                  max="2000"
                  value={throttle}
                  onChange={(e) => handleThrottleChange(e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)', cursor: 'pointer' }}
                />
              </div>

              {/* Pitch (CH2) */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Pitch / Forward-Back (CH2)</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{pitch} µs</span>
                </div>
                <input
                  type="range"
                  min="1000"
                  max="2000"
                  value={pitch}
                  onChange={(e) => handleCopterAxis('pitch', e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)', cursor: 'pointer' }}
                />
              </div>

              {/* Roll (CH1) */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Roll / Bank (CH1)</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{roll} µs</span>
                </div>
                <input
                  type="range"
                  min="1000"
                  max="2000"
                  value={roll}
                  onChange={(e) => handleCopterAxis('roll', e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)', cursor: 'pointer' }}
                />
              </div>

              {/* Yaw (CH4) */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Yaw / Rotation (CH4)</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{yaw} µs</span>
                </div>
                <input
                  type="range"
                  min="1000"
                  max="2000"
                  value={yaw}
                  onChange={(e) => handleCopterAxis('yaw', e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)', cursor: 'pointer' }}
                />
              </div>

              {/* Center flight controls */}
              <div style={{ display: 'flex', justifyContent: 'center', marginTop: '4px' }}>
                <button onClick={centerSticks} className="btn btn--sm">■ Center Sticks / Hover</button>
              </div>

              {/* ARM / DISARM and Flight Mode Controls */}
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '8px', paddingTop: '12px', borderTop: '1px solid var(--border)' }}>
                <button
                  onClick={handleArmToggle}
                  className={`btn btn--sm ${isArmed ? 'btn--primary' : 'btn--danger'}`}
                  style={{ minWidth: '100px' }}
                >
                  {isArmed ? '🟢 ARMED' : '🔴 DISARMED'}
                </button>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>Flight Mode</span>
                  <select
                    value={flightMode}
                    onChange={handleModeChange}
                    className="input"
                    style={{ flex: 1, fontSize: '12px', padding: '4px 8px' }}
                  >
                    <option value="STABILIZE">STABILIZE</option>
                    <option value="ALT_HOLD">ALT_HOLD</option>
                    <option value="LOITER">LOITER</option>
                    <option value="RTL">RTL</option>
                    <option value="LAND">LAND</option>
                    <option value="GUIDED">GUIDED</option>
                  </select>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Throttle slider */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Throttle (CH3)</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{throttle} µs</span>
                </div>
                <input
                  type="range"
                  min="1000"
                  max="2000"
                  value={throttle}
                  onChange={(e) => handleThrottleChange(e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)', cursor: 'pointer' }}
                />
              </div>

              {/* Steering slider */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Steering (CH1)</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{steering} µs</span>
                </div>
                <input
                  type="range"
                  min="1000"
                  max="2000"
                  value={steering}
                  onChange={(e) => handleSteeringChange(e.target.value)}
                  style={{ width: '100%', accentColor: 'var(--accent-blue)', cursor: 'pointer' }}
                />
              </div>

              {/* D-Pad Quick Actions */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', maxWidth: '240px', margin: '0 auto' }}>
                <div />
                <button onClick={() => drive(1750, 1500)} className="btn btn--sm">▲ Fwd</button>
                <div />
                <button onClick={() => drive(1500, 1300)} className="btn btn--sm">◀ Left</button>
                <button onClick={stop} className="btn btn--danger btn--sm">■ Stop</button>
                <button onClick={() => drive(1500, 1700)} className="btn btn--sm">Right ▶</button>
                <div />
                <button onClick={() => drive(1250, 1500)} className="btn btn--sm">▼ Rev</button>
                <div />
              </div>
            </div>
          )}
        </div>

        {/* GPS & Coordinate Telemetry */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">📍 Spatial Coordinates & Orientation</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Latitude</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{telemetry.gps.lat.toFixed(6)}°</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Longitude</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{telemetry.gps.lon.toFixed(6)}°</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Altitude (MSL)</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{telemetry.gps.alt.toFixed(1)} m</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '6px' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Roll / Pitch</span>
              <span style={{ fontFamily: 'var(--font-mono)' }}>{rollDeg}° / {pitchDeg}°</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-secondary)' }}>Raw RC Channels</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                {telemetry.rc.slice(0, 4).join(' | ')}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Real-time Diagnostics Log */}
      <LogConsole logs={logs} />
    </div>
  );
}
