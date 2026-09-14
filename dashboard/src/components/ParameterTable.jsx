import React, { useState, useMemo } from 'react';
import { ParameterRow } from './ParameterRow';

export function ParameterTable({ parameters, onSaveParameter, onRefresh, onExport }) {
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState('param_index');
  const [sortAsc, setSortAsc] = useState(true);

  const filteredParams = useMemo(() => {
    return parameters
      .filter((p) => p.param_id.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => {
        let res = 0;
        if (sortField === 'param_id') {
          res = a.param_id.localeCompare(b.param_id);
        } else if (sortField === 'value') {
          res = a.value - b.value;
        } else {
          res = a.param_index - b.param_index;
        }
        return sortAsc ? res : -res;
      });
  }, [parameters, search, sortField, sortAsc]);

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  return (
    <div className="card" style={{ gap: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Filter parameters by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input"
          style={{ maxWidth: '320px' }}
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
            Showing {filteredParams.length} of {parameters.length}
          </span>
          <button onClick={onRefresh} className="btn btn--sm">↻ Refresh</button>
          <button onClick={onExport} className="btn btn--sm">⬇ Export JSON</button>
        </div>
      </div>

      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th onClick={() => toggleSort('param_id')} style={{ cursor: 'pointer' }}>
                Parameter {sortField === 'param_id' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th onClick={() => toggleSort('value')} style={{ cursor: 'pointer' }}>
                Value {sortField === 'value' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th>Type</th>
              <th onClick={() => toggleSort('param_index')} style={{ cursor: 'pointer' }}>
                Index {sortField === 'param_index' ? (sortAsc ? '▲' : '▼') : ''}
              </th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredParams.length > 0 ? (
              filteredParams.map((param) => (
                <ParameterRow
                  key={param.param_id}
                  param={param}
                  onSave={onSaveParameter}
                />
              ))
            ) : (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '24px' }}>
                  No matching parameters found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
