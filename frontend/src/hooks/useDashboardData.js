import { useState, useEffect, useCallback } from 'react';
import { useWebSocket, Channels, ConnectionState } from './useWebSocket';
import * as api from '../services/api';

/**
 * Custom hook for managing dashboard data with real-time updates
 * 
 * Combines REST API calls for initial data with WebSocket for real-time updates
 */
export function useDashboardData() {
  // Dashboard overview state
  const [overview, setOverview] = useState({
    total_logs: 0,
    total_anomalies: 0,
    total_alerts: 0,
    logs_per_minute: 0,
    error_rate: 0,
    anomaly_rate: 0,
    pipeline_status: 'unknown',
    kafka_connected: false,
    services_count: 0,
    last_log_timestamp: null,
  });

  // Real-time stats
  const [stats, setStats] = useState({
    logs_per_second: 0,
    errors_per_second: 0,
    anomalies_per_second: 0,
    active_services: 0,
  });

  // Logs
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(true);

  // Alerts
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);

  // Services
  const [services, setServices] = useState([]);
  const [servicesLoading, setServicesLoading] = useState(true);

  // System health
  const [systemHealth, setSystemHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);

  // Loading and error states
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // WebSocket connection
  const {
    connectionState,
    isConnected,
  } = useWebSocket({
    channels: [Channels.ALL],
    onStats: (data) => {
      setStats({
        logs_per_second: data.logs_per_second || 0,
        errors_per_second: data.errors_per_second || 0,
        anomalies_per_second: data.anomalies_per_second || 0,
        active_services: data.active_services || 0,
      });
      
      // Update overview data from stats
      if (data.data) {
        setOverview((prev) => ({
          ...prev,
          total_logs: data.data.total_logs || prev.total_logs,
          total_anomalies: data.data.total_anomalies || prev.total_anomalies,
          total_alerts: data.data.total_alerts || prev.total_alerts,
          pipeline_status: data.pipeline_status || prev.pipeline_status,
        }));
      }
    },
    onLog: (log) => {
      setLogs((prev) => [log, ...prev.slice(0, 99)]); // Keep last 100 logs
    },
    onAlert: (alert) => {
      setAlerts((prev) => [
        {
          id: alert.alert_id || Date.now(),
          title: alert.alert_type || 'Alert',
          service: alert.service || 'Unknown',
          severity: alert.severity || 'warning',
          time: 'Just now',
          status: 'active',
          ...alert,
        },
        ...prev.slice(0, 99),
      ]);
    },
    onHealth: (health) => {
      if (health.component === 'system') {
        fetchSystemHealth();
      }
    },
  });

  /**
   * Fetch dashboard overview from API
   */
  const fetchOverview = useCallback(async () => {
    try {
      const data = await api.getDashboardOverview();
      setOverview(data);
    } catch (err) {
      console.error('Failed to fetch overview:', err);
      setError(err.message);
    }
  }, []);

  /**
   * Fetch real-time stats from API
   */
  const fetchStats = useCallback(async () => {
    try {
      const data = await api.getRealTimeStats();
      // Calculate per-second rates from the window data
      const windowSeconds = data.window_duration_seconds || 15;
      setStats({
        logs_per_second: Math.round((data.logs_in_window / windowSeconds) * 10) / 10,
        errors_per_second: Math.round((data.errors_in_window / windowSeconds) * 10) / 10,
        anomalies_per_second: Math.round((data.anomalies_in_window / windowSeconds) * 10) / 10,
        active_services: data.active_services || 0,
      });
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  }, []);

  /**
   * Fetch recent logs from API
   */
  const fetchLogs = useCallback(async (options = {}) => {
    try {
      setLogsLoading(true);
      const data = await api.getRecentLogs(options);
      setLogs(data);
    } catch (err) {
      console.error('Failed to fetch logs:', err);
    } finally {
      setLogsLoading(false);
    }
  }, []);

  /**
   * Fetch recent alerts from API
   */
  const fetchAlerts = useCallback(async (options = {}) => {
    try {
      setAlertsLoading(true);
      const data = await api.getRecentAlerts(options);
      // Transform alerts to match frontend format
      const transformedAlerts = data.map((alert, index) => ({
        id: alert.id || index,
        title: alert.alert_type || alert.title || 'Alert',
        description: alert.description || alert.message || '',
        severity: alert.severity || 'warning',
        service: alert.service || 'Unknown',
        time: formatTime(alert.timestamp),
        status: alert.status || 'active',
        ...alert,
      }));
      setAlerts(transformedAlerts);
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    } finally {
      setAlertsLoading(false);
    }
  }, []);

  /**
   * Fetch service statistics from API
   */
  const fetchServices = useCallback(async () => {
    try {
      setServicesLoading(true);
      const data = await api.getServiceStatistics(20);
      // Transform services to match frontend format
      const transformedServices = data.map((service, index) => ({
        id: index + 1,
        name: service.service_name || service.name,
        status: getServiceStatus(service),
        uptime: service.uptime || 99.9,
        responseTime: service.avg_response_time_ms || 100,
        requests: service.total_logs || 0,
        cpu: service.cpu_usage || 50,
        memory: service.memory_usage || 60,
        lastCheck: 'Just now',
        errorCount: service.error_count || 0,
        anomalyCount: service.anomaly_count || 0,
        ...service,
      }));
      setServices(transformedServices);
    } catch (err) {
      console.error('Failed to fetch services:', err);
    } finally {
      setServicesLoading(false);
    }
  }, []);

  /**
   * Fetch system health from API
   */
  const fetchSystemHealth = useCallback(async () => {
    try {
      setHealthLoading(true);
      const data = await api.getSystemHealth();
      setSystemHealth(data);
    } catch (err) {
      console.error('Failed to fetch system health:', err);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  /**
   * Refresh all data
   */
  const refreshAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    await Promise.all([
      fetchOverview(),
      fetchStats(),
      fetchLogs(),
      fetchAlerts(),
      fetchServices(),
      fetchSystemHealth(),
    ]);
    
    setIsLoading(false);
  }, [fetchOverview, fetchStats, fetchLogs, fetchAlerts, fetchServices, fetchSystemHealth]);

  // Initial data fetch
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Periodic refresh (every 30 seconds for overview, every 5 seconds for stats)
  useEffect(() => {
    const overviewInterval = setInterval(() => {
      fetchOverview();
      fetchServices();
    }, 30000);

    // Poll for real-time stats every 5 seconds (for chart updates)
    const statsInterval = setInterval(() => {
      fetchStats();
    }, 5000);

    return () => {
      clearInterval(overviewInterval);
      clearInterval(statsInterval);
    };
  }, [fetchOverview, fetchServices, fetchStats]);

  return {
    // Data
    overview,
    stats,
    logs,
    alerts,
    services,
    systemHealth,
    
    // Loading states
    isLoading,
    logsLoading,
    alertsLoading,
    servicesLoading,
    healthLoading,
    
    // Error
    error,
    
    // Connection state
    connectionState,
    isConnected,
    
    // Actions
    refreshAll,
    fetchStats,
    fetchLogs,
    fetchAlerts,
    fetchServices,
    fetchSystemHealth,
  };
}

/**
 * Helper function to determine service status from stats
 */
function getServiceStatus(service) {
  if (service.error_rate > 0.1) return 'critical';
  if (service.error_rate > 0.05 || service.anomaly_count > 5) return 'warning';
  return 'healthy';
}

/**
 * Helper function to format timestamp as relative time
 */
function formatTime(timestamp) {
  if (!timestamp) return 'Unknown';
  
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  
  if (diffSec < 60) return 'Just now';
  if (diffMin < 60) return `${diffMin} min${diffMin > 1 ? 's' : ''} ago`;
  if (diffHour < 24) return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
}

export default useDashboardData;
