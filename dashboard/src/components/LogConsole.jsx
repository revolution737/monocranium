import React, { useState } from 'react';

export function LogConsole({ logs = [], onClear }) {
  const [filter, setFilter] = useState('');

  const filteredLogs = logs.filter((log) =>
    log.text.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="card" style={{ height: '240px' }}>
      <div className="card-header" style={{ marginBottom: '8px' }}>
        <span className="card-title">Event & Diagnostic Console</span>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input
            type="text"
            placeholder="Filter log..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input"
            style={{ width: '160px', padding: '2px 8px', fontSize: '11px', height: '24px' }}
          />
          {onClear && (
            <button onClick={onClear} className="btn btn--ghost btn--sm" style={{ padding: '2px 8px' }}>
              Clear
            </button>
          )}
        </div>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          backgroundColor: 'var(--bg-primary)',
          borderRadius: 'var(--radius-sm)',
          padding: '8px 12px',
          fontFamily: 'var(--font-mono)',
          fontSize: '11px',
          display: 'flex',
          flexDirection: 'column-reverse',
          gap: '4px',
          border: '1px solid var(--border)',
        }}
      >
        {filteredLogs.map((log) => {
          const color =
            log.type === 'error'
              ? 'var(--accent-red)'
              : log.type === 'success'
              ? 'var(--accent-green)'
              : 'var(--text-secondary)';
          return (
            <div key={log.id} style={{ display: 'flex', gap: '8px', lineHeight: 1.4 }}>
              <span style={{ color: 'var(--text-muted)' }}>[{log.time}]</span>
              <span style={{ color }}>{log.text}</span>
            </div>
          );
        })}
        {filteredLogs.length === 0 && (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '16px' }}>
            No logs recorded yet.
          </div>
        )}
      </div>
    </div>
  );
}
