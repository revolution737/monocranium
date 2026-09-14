import { useState, useEffect, useCallback, useRef } from 'react';

const MAX_LOGS = 200;
const MAX_HISTORY_POINTS = 30;

export function useTelemetry(ws) {
  const { isConnected, sendMessage, lastMessage } = ws;

  const [vehicles, setVehicles] = useState([]);
  const [activeSystemId, setActiveSystemId] = useState(2);
  const [parameters, setParameters] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState([]);
  const [logs, setLogs] = useState([]);

  const [telemetry, setTelemetry] = useState({
    attitude: { roll: 0, pitch: 0, yaw: 0 },
    gps: { lat: 28.6139, lon: 77.2090, alt: 0, fix_type: 3, satellites: 12 },
    battery: { voltage: 11.1, current: 0.0, remaining: 100 },
    rc: [1500, 1500, 1500, 1500],
    speed: 0.0,
    history: [],
  });

  const appendLog = useCallback((text, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [{ id: Date.now() + Math.random(), time: timestamp, text, type }, ...prev].slice(0, MAX_LOGS));
  }, []);

  // Handle incoming messages
  useEffect(() => {
    if (!lastMessage) return;

    // Handle responses to request actions
    if (lastMessage.response_to) {
      const { response_to, success, data, error } = lastMessage;
      if (!success) {
        appendLog(`Error in ${response_to}: ${error}`, 'error');
        return;
      }

      if (response_to === 'get_vehicles') {
        setVehicles(data || []);
        if (data && data.length > 0 && !data.some((v) => v.system_id === activeSystemId)) {
          setActiveSystemId(data[0].system_id);
        }
      } else if (response_to === 'get_parameters') {
        setParameters(data || []);
        appendLog(`Loaded ${(data || []).length} parameters`, 'success');
      } else if (response_to === 'get_connection_status') {
        setConnectionStatus(data || []);
      } else if (response_to === 'run_autoconfig') {
        setVehicles(data || []);
        appendLog(`Auto-config scan finished. Discovered ${data?.length || 0} vehicles`, 'success');
      }
      return;
    }

    // Handle pushed telemetry / system events
    if (lastMessage.event) {
      const { event, data } = lastMessage;

      if (event === 'vehicle.discovered') {
        setVehicles((prev) => {
          const exists = prev.some((v) => v.system_id === data.system_id);
          return exists ? prev.map((v) => (v.system_id === data.system_id ? data : v)) : [...prev, data];
        });
        appendLog(`Vehicle discovered: SYSID ${data.system_id} (${data.vehicle_type})`, 'success');
      } else if (event === 'vehicle.updated') {
        setVehicles((prev) => prev.map((v) => (v.system_id === data.system_id ? data : v)));
      } else if (event === 'vehicle.lost') {
        setVehicles((prev) => prev.filter((v) => v.system_id !== data.system_id));
        appendLog(`Vehicle connection lost: SYSID ${data.system_id}`, 'error');
      } else if (event === 'param.updated') {
        setParameters((prev) => {
          const updated = data.param;
          const idx = prev.findIndex((p) => p.param_id === updated.param_id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = updated;
            return next;
          }
          return [...prev, updated];
        });
        appendLog(`Parameter updated: ${data.param.param_id} = ${data.param.value}`, 'info');
      } else if (event === 'param.bulk_loaded') {
        sendMessage({ action: 'get_parameters', system_id: data.system_id });
      } else if (event === 'telemetry.attitude') {
        setTelemetry((prev) => {
          const newHistory = [
            ...prev.history,
            { time: Date.now(), yaw: (data.yaw * 180) / Math.PI, speed: prev.speed },
          ].slice(-MAX_HISTORY_POINTS);

          return {
            ...prev,
            attitude: { roll: data.roll, pitch: data.pitch, yaw: data.yaw },
            history: newHistory,
          };
        });
      } else if (event === 'telemetry.gps') {
        setTelemetry((prev) => ({
          ...prev,
          gps: {
            lat: data.lat,
            lon: data.lon,
            alt: data.alt,
            fix_type: data.fix_type,
            satellites: data.satellites,
          },
        }));
      } else if (event === 'telemetry.battery') {
        setTelemetry((prev) => ({
          ...prev,
          battery: {
            voltage: data.voltage,
            current: data.current,
            remaining: data.remaining,
          },
        }));
      } else if (event === 'telemetry.rc') {
        setTelemetry((prev) => ({
          ...prev,
          rc: data.channels || prev.rc,
        }));
      }
    }
  }, [lastMessage, activeSystemId, appendLog, sendMessage]);

  // Query vehicles on connect
  useEffect(() => {
    if (isConnected) {
      appendLog('Connected to Core Bridge WebSocket', 'success');
      sendMessage({ action: 'get_vehicles' });
      sendMessage({ action: 'get_connection_status' });
    } else {
      appendLog('Disconnected from Core Bridge WebSocket. Reconnecting...', 'error');
    }
  }, [isConnected, appendLog, sendMessage]);

  // Query parameters when active vehicle changes
  useEffect(() => {
    if (isConnected && activeSystemId) {
      sendMessage({ action: 'get_parameters', system_id: activeSystemId });
    }
  }, [isConnected, activeSystemId, sendMessage]);

  const sendRcOverride = useCallback(
    (throttle, steering) => {
      return sendMessage({
        action: 'rc_override',
        system_id: activeSystemId,
        payload: { throttle_pwm: throttle, steering_pwm: steering },
      });
    },
    [activeSystemId, sendMessage]
  );

  const setParameter = useCallback(
    (paramId, value) => {
      return sendMessage({
        action: 'set_parameter',
        system_id: activeSystemId,
        payload: { param_id: paramId, value: parseFloat(value) },
      });
    },
    [activeSystemId, sendMessage]
  );

  const refreshParameters = useCallback(() => {
    return sendMessage({ action: 'get_parameters', system_id: activeSystemId });
  }, [activeSystemId, sendMessage]);

  const runAutoConfig = useCallback(
    (endpoints) => {
      return sendMessage({ action: 'run_autoconfig', payload: { endpoints } });
    },
    [sendMessage]
  );

  return {
    vehicles,
    activeSystemId,
    setActiveSystemId,
    parameters,
    connectionStatus,
    telemetry,
    logs,
    sendRcOverride,
    setParameter,
    refreshParameters,
    runAutoConfig,
  };
}
