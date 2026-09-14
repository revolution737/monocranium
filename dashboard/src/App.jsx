import React, { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useTelemetry } from './hooks/useTelemetry';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { SetupPage } from './pages/SetupPage';
import { DashboardPage } from './pages/DashboardPage';
import { ParametersPage } from './pages/ParametersPage';

export default function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const ws = useWebSocket();
  const {
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
  } = useTelemetry(ws);

  const activeVehicle = vehicles.find((v) => v.system_id === activeSystemId) || vehicles[0];

  const getPageTitle = () => {
    switch (currentPage) {
      case 'setup':
        return 'Autonomous Setup & Handshake';
      case 'parameters':
        return 'MAVLink Parameters';
      case 'dashboard':
      default:
        return 'Flight Telemetry & Actuation';
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        vehicles={vehicles}
        activeSystemId={activeSystemId}
        onSelectVehicle={setActiveSystemId}
      />

      <div className="main-content">
        <Header
          title={getPageTitle()}
          isConnected={ws.isConnected}
          activeVehicle={activeVehicle}
        />

        <main className="content-body">
          {currentPage === 'setup' && (
            <SetupPage
              vehicles={vehicles}
              activeVehicle={activeVehicle}
              onRunAutoConfig={runAutoConfig}
              connectionStatus={connectionStatus}
            />
          )}

          {currentPage === 'dashboard' && (
            <DashboardPage
              telemetry={telemetry}
              logs={logs}
              onSendRcOverride={sendRcOverride}
              activeVehicle={activeVehicle}
            />
          )}

          {currentPage === 'parameters' && (
            <ParametersPage
              parameters={parameters}
              activeVehicle={activeVehicle}
              onSaveParameter={setParameter}
              onRefresh={refreshParameters}
            />
          )}
        </main>
      </div>
    </div>
  );
}
