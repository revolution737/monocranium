import React from 'react';
import { ResponsiveContainer, LineChart, Line } from 'recharts';

export function TelemetryGauge({ title, value, unit, history = [], color = '#58a6ff', dataKey = 'value' }) {
  const chartData = history.map((pt, i) => ({
    i,
    value: typeof pt === 'object' ? pt[dataKey] ?? 0 : pt,
  }));

  return (
    <div className="card" style={{ minWidth: '180px', flex: '1 1 200px' }}>
      <div className="card-header" style={{ marginBottom: '8px' }}>
        <span className="card-title" style={{ fontSize: '12px' }}>{title}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '8px' }}>
        <span style={{ fontSize: '24px', fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-primary)' }}>
          {value !== undefined && value !== null ? value : '--'}
        </span>
        {unit && <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{unit}</span>}
      </div>

      <div style={{ width: '100%', height: '36px', marginTop: 'auto' }}>
        {chartData.length > 1 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <Line
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', color: 'var(--text-muted)', fontSize: '11px' }}>
            Awaiting history...
          </div>
        )}
      </div>
    </div>
  );
}
