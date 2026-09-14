import React from 'react';
import { ParameterTable } from '../components/ParameterTable';

export function ParametersPage({
  parameters = [],
  activeVehicle,
  onSaveParameter,
  onRefresh,
}) {
  const handleExport = () => {
    const jsonStr = JSON.stringify(parameters, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `monocranium_sysid_${activeVehicle?.system_id || 2}_params.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Vehicle Parameter Configuration</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
            Inspect and dynamically modify onboard MAVLink parameters in real time.
          </p>
        </div>
      </div>

      <ParameterTable
        parameters={parameters}
        onSaveParameter={onSaveParameter}
        onRefresh={onRefresh}
        onExport={handleExport}
      />
    </div>
  );
}
