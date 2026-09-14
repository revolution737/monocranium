import React, { useState } from 'react';

export function ParameterRow({ param, onSave }) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(param.value);

  const handleSave = () => {
    onSave(param.param_id, editValue);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setEditValue(param.value);
    setIsEditing(false);
  };

  return (
    <tr>
      <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--accent-blue)' }}>
        {param.param_id}
      </td>
      <td>
        {isEditing ? (
          <input
            type="number"
            step="any"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            className="input"
            style={{ width: '120px', padding: '4px 8px', fontSize: '13px' }}
            autoFocus
          />
        ) : (
          <span style={{ fontFamily: 'var(--font-mono)' }}>{param.value}</span>
        )}
      </td>
      <td style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>
        {param.param_type === 9 ? 'REAL32' : param.param_type === 6 ? 'INT32' : param.param_type}
      </td>
      <td style={{ color: 'var(--text-secondary)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>
        #{param.param_index}
      </td>
      <td style={{ textAlign: 'right' }}>
        {isEditing ? (
          <div style={{ display: 'inline-flex', gap: '6px' }}>
            <button onClick={handleSave} className="btn btn--primary btn--sm">Save</button>
            <button onClick={handleCancel} className="btn btn--ghost btn--sm">Cancel</button>
          </div>
        ) : (
          <button onClick={() => setIsEditing(true)} className="btn btn--ghost btn--sm">Edit</button>
        )}
      </td>
    </tr>
  );
}
