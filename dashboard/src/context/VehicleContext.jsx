import React, { createContext, useContext, useState } from 'react';

const VehicleContext = createContext(null);

export function VehicleProvider({ children }) {
  const [activeSystemId, setActiveSystemId] = useState(2);

  return (
    <VehicleContext.Provider value={{ activeSystemId, setActiveSystemId }}>
      {children}
    </VehicleContext.Provider>
  );
}

export function useVehicleContext() {
  const context = useContext(VehicleContext);
  if (!context) {
    throw new Error('useVehicleContext must be used within a VehicleProvider');
  }
  return context;
}
