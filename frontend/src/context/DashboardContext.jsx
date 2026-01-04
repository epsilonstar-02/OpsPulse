import { createContext, useContext } from 'react';
import { useDashboardData } from '../hooks/useDashboardData';

const DashboardContext = createContext(null);

/**
 * Dashboard data provider component
 * Provides dashboard data and WebSocket connection to all child components
 */
export function DashboardProvider({ children }) {
  const dashboardData = useDashboardData();

  return (
    <DashboardContext.Provider value={dashboardData}>
      {children}
    </DashboardContext.Provider>
  );
}

/**
 * Hook to access dashboard data from context
 */
export function useDashboard() {
  const context = useContext(DashboardContext);
  
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  
  return context;
}

export default DashboardContext;
