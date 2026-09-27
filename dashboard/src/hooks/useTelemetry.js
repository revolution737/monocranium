import { useState, useEffect, useCallback } from 'react';

const MAX_LOGS = 200;
const MAX_HISTORY_POINTS = 30;

const emptyTelemetry = () => ({
  attitude: { roll: null, pitch: null, yaw: null },
  gps: { lat: null, lon: null, alt: null, fix_type: null, satellites: null },
  battery: { voltage: null, current: null, remaining: null },
  rc: [],
  speed: null,
  history: [],
});

export function useTelemetry(ws) {
  const { isConnected, sendMessage, subscribeMessage, subscribeConnection } = ws;

  const [vehicles, setVehicles] = useState([]);
  const [activeSystemId, setActiveSystemId] = useState(null);
  const [statusBySystem, setStatusBySystem] = useState({});
  const [parameters, setParameters] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState([]);
  const [logs, setLogs] = useState([]);

  const [telemetry, setTelemetry] = useState(emptyTelemetry);

  const selectVehicle = useCallback((systemId) => {
    setActiveSystemId(systemId);
    setTelemetry(emptyTelemetry());
  }, []);

  const appendLog = useCallback((text, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [{ id: Date.now() + Math.random(), time: timestamp, text, type }, ...prev].slice(0, MAX_LOGS));
  }, []);

  // Process every WebSocket frame, including bursts of parameter updates.
  useEffect(() => {
    const handleMessage = (lastMessage) => {

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
          selectVehicle(data[0].system_id);
        }
      } else if (response_to === 'get_parameters') {
        setParameters(data || []);
        appendLog(`Loaded ${(data || []).length} parameters`, 'success');
      } else if (response_to === 'get_connection_status') {
        setConnectionStatus(data || []);
      } else if (response_to === 'run_autoconfig') {
        setVehicles(data || []);
        appendLog(`Auto-config scan finished. Discovered ${data?.length || 0} vehicles`, 'success');
      } else if (response_to === 'arm_vehicle') {
        appendLog(`Vehicle SYSID ${data?.system_id} ${data?.armed ? 'ARMED' : 'DISARMED'} successfully`, 'success');
      } else if (response_to === 'set_flight_mode') {
        appendLog(`Vehicle SYSID ${data?.system_id} flight mode set to ${data?.mode}`, 'success');
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
        if (!activeSystemId) selectVehicle(data.system_id);
        appendLog(`Vehicle discovered: SYSID ${data.system_id} (${data.vehicle_type})`, 'success');
      } else if (event === 'vehicle.updated') {
        setVehicles((prev) => prev.map((v) => (v.system_id === data.system_id ? data : v)));
      } else if (event === 'vehicle.lost') {
        setVehicles((prev) => prev.filter((v) => v.system_id !== data.system_id));
        setStatusBySystem((prev) => {
          const next = { ...prev };
          delete next[data.system_id];
          return next;
        });
        if (data.system_id === activeSystemId) {
          selectVehicle(null);
          setParameters([]);
          sendMessage({ action: 'get_vehicles' });
        }
        appendLog(`Vehicle connection lost: SYSID ${data.system_id}`, 'error');
      } else if (event === 'vehicle.status') {
        setStatusBySystem((prev) => ({ ...prev, [data.system_id]: data }));
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
        if (data.system_id && data.system_id !== activeSystemId) return;
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
        if (data.system_id && data.system_id !== activeSystemId) return;
        setTelemetry((prev) => ({
          ...prev,
          gps: {
            ...prev.gps,
            lat: data.lat,
            lon: data.lon,
            alt: data.alt,
            fix_type: data.fix_type,
            satellites: data.satellites,
          },
        }));
      } else if (event === 'telemetry.position' || event === 'telemetry.hud') {
        if (data.system_id && data.system_id !== activeSystemId) return;
        setTelemetry((prev) => ({
          ...prev,
          speed: data.speed ?? prev.speed,
          gps: {
            ...prev.gps,
            lat: data.lat ?? prev.gps.lat,
            lon: data.lon ?? prev.gps.lon,
            alt: data.alt ?? prev.gps.alt,
            relative_alt: data.relative_alt ?? prev.gps.relative_alt,
          },
        }));
      } else if (event === 'telemetry.battery') {
        if (data.system_id && data.system_id !== activeSystemId) return;
        setTelemetry((prev) => ({
          ...prev,
          battery: {
            voltage: data.voltage,
            current: data.current,
            remaining: data.remaining,
          },
        }));
      } else if (event === 'telemetry.rc') {
        if (data.system_id && data.system_id !== activeSystemId) return;
        setTelemetry((prev) => ({
          ...prev,
          rc: data.channels || prev.rc,
        }));
      }
    }
    };
    return subscribeMessage(handleMessage);
  }, [subscribeMessage, activeSystemId, appendLog, sendMessage, selectVehicle]);

  // React to the transport lifecycle so disconnected data never appears live.
  useEffect(() => {
    const handleConnection = (connected) => {
      if (connected) {
        appendLog('Connected to Core Bridge WebSocket', 'success');
        sendMessage({ action: 'get_vehicles' });
        sendMessage({ action: 'get_connection_status' });
      } else {
        selectVehicle(null);
        setVehicles([]);
        setParameters([]);
        setStatusBySystem({});
        appendLog('Disconnected from Core Bridge WebSocket. Reconnecting...', 'error');
      }
    };
    return subscribeConnection(handleConnection);
  }, [subscribeConnection, appendLog, sendMessage, selectVehicle]);

  // Query parameters when active vehicle changes
  useEffect(() => {
    if (isConnected && activeSystemId) {
      sendMessage({ action: 'get_parameters', system_id: activeSystemId });
    }
  }, [isConnected, activeSystemId, sendMessage]);

  const sendRcOverride = useCallback(
    (throttle, steering = 1500, pitch = 0, yaw = 0, roll = null) => {
      const rollVal = roll !== null ? roll : steering;
      return sendMessage({
        action: 'rc_override',
        system_id: activeSystemId,
        payload: {
          throttle_pwm: throttle,
          steering_pwm: steering,
          roll_pwm: rollVal,
          pitch_pwm: pitch,
          yaw_pwm: yaw,
        },
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

  const armVehicle = useCallback(
    (arm, targetSystemId) => {
      const sysId = targetSystemId ?? activeSystemId;
      return sendMessage({
        action: 'arm_vehicle',
        system_id: sysId,
        payload: { arm },
      });
    },
    [activeSystemId, sendMessage]
  );

  const setFlightMode = useCallback(
    (mode, targetSystemId) => {
      const sysId = targetSystemId ?? activeSystemId;
      return sendMessage({
        action: 'set_flight_mode',
        system_id: sysId,
        payload: { mode },
      });
    },
    [activeSystemId, sendMessage]
  );

  return {
    vehicles,
    activeSystemId,
    setActiveSystemId: selectVehicle,
    activeVehicleStatus: statusBySystem[activeSystemId] ?? null,
    parameters,
    connectionStatus,
    telemetry,
    logs,
    sendRcOverride,
    setParameter,
    refreshParameters,
    runAutoConfig,
    armVehicle,
    setFlightMode,
  };
}
