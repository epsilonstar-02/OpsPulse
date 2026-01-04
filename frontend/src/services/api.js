/**
 * API Service for OpsPulse Backend
 * 
 * This module provides functions to interact with the OpsPulse backend API.
 * Base URL can be configured via environment variable VITE_API_URL
 * 
 * In development with Vite proxy, use empty string to leverage the proxy config.
 * In production, set VITE_API_URL to the backend URL.
 */

// Use backend URL directly in development, or configured URL in production
const API_BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8001' : '');

/**
 * Generic fetch wrapper with error handling
 */
async function fetchAPI(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
    },
  };
  
  try {
    const response = await fetch(url, { ...defaultOptions, ...options });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  } catch (error) {
    // If backend is unavailable, throw a more helpful error
    if (error.message === 'Failed to fetch') {
      throw new Error('Backend server is not available. Please ensure the backend is running on port 8001.');
    }
    throw error;
  }
}

// ============== Analytics API ==============

/**
 * Get dashboard overview with key metrics
 */
export async function getDashboardOverview() {
  return fetchAPI('/api/analytics/overview');
}

/**
 * Get complete analytics summary
 * @param {string} timeRange - Time range: 'last_15_minutes', 'last_hour', 'last_24_hours', 'last_7_days'
 */
export async function getAnalyticsSummary(timeRange = 'last_hour') {
  return fetchAPI(`/api/analytics/summary?time_range=${timeRange}`);
}

/**
 * Get breakdown of logs by severity level
 */
export async function getLogLevelBreakdown() {
  return fetchAPI('/api/analytics/log-levels');
}

/**
 * Get statistics for all monitored services
 * @param {number} limit - Maximum services to return
 * @param {string} sortBy - Sort field: 'anomaly_count', 'error_count', 'total_logs'
 */
export async function getServiceStatistics(limit = 20, sortBy = 'anomaly_count') {
  return fetchAPI(`/api/analytics/services?limit=${limit}&sort_by=${sortBy}`);
}

/**
 * Get detailed statistics for a specific service
 * @param {string} serviceName - Name of the service
 */
export async function getServiceDetails(serviceName) {
  return fetchAPI(`/api/analytics/services/${encodeURIComponent(serviceName)}`);
}

/**
 * Get real-time stats
 */
export async function getRealTimeStats() {
  return fetchAPI('/api/analytics/realtime');
}

/**
 * Get time series data for charts
 * @param {string} metric - Metric type: 'logs', 'errors', 'anomalies', 'latency'
 * @param {string} interval - Interval: 'minute', 'hour', 'day'
 */
export async function getTimeSeriesData(metric = 'logs', interval = 'minute') {
  return fetchAPI(`/api/analytics/timeseries?metric=${metric}&interval=${interval}`);
}

// ============== Logs API ==============

/**
 * Get recent log entries
 * @param {Object} options - Query options
 * @param {number} options.limit - Number of logs to return
 * @param {string} options.service - Filter by service name
 * @param {string} options.level - Filter by log level
 * @param {boolean} options.anomalyOnly - Only return anomaly logs
 */
export async function getRecentLogs({ limit = 100, service, level, anomalyOnly = false } = {}) {
  const params = new URLSearchParams();
  params.append('limit', limit);
  if (service) params.append('service', service);
  if (level) params.append('level', level);
  if (anomalyOnly) params.append('anomaly_only', 'true');
  
  return fetchAPI(`/api/logs/recent?${params}`);
}

/**
 * Get log stream information
 */
export async function getLogStreamInfo() {
  return fetchAPI('/api/logs/stream');
}

/**
 * Trigger log generation
 * @param {number} count - Number of logs to generate
 * @param {number} anomalyRate - Probability of anomalies (0-1)
 */
export async function triggerLogGeneration(count = 100, anomalyRate = 0.05) {
  return fetchAPI(`/api/logs/generate?count=${count}&anomaly_rate=${anomalyRate}`, {
    method: 'POST',
  });
}

// ============== Alerts API ==============

/**
 * Get recent alerts
 * @param {Object} options - Query options
 * @param {number} options.limit - Number of alerts to return
 * @param {string} options.status - Filter by status: 'active', 'acknowledged', 'resolved'
 * @param {string} options.severity - Filter by severity: 'critical', 'warning', 'info'
 */
export async function getRecentAlerts({ limit = 100, status, severity } = {}) {
  const params = new URLSearchParams();
  params.append('limit', limit);
  if (status) params.append('status', status);
  if (severity) params.append('severity', severity);
  
  return fetchAPI(`/api/alerts/recent?${params}`);
}

/**
 * Get alert by ID
 * @param {string} alertId - Alert ID
 */
export async function getAlert(alertId) {
  return fetchAPI(`/api/alerts/${alertId}`);
}

/**
 * Update alert status
 * @param {string} alertId - Alert ID
 * @param {string} status - New status: 'acknowledged', 'resolved'
 */
export async function updateAlertStatus(alertId, status) {
  return fetchAPI(`/api/alerts/${alertId}/status?status=${status}`, {
    method: 'PUT',
  });
}

/**
 * Get remediation for an alert
 * @param {string} alertId - Alert ID
 */
export async function getRemediation(alertId) {
  return fetchAPI(`/api/alerts/${alertId}/remediation`);
}

/**
 * Trigger remediation query to RAG
 * @param {string} alertId - Alert ID
 */
export async function triggerRemediation(alertId) {
  return fetchAPI(`/api/alerts/${alertId}/remediation`, {
    method: 'POST',
  });
}

// ============== System API ==============

/**
 * Get comprehensive system health status
 */
export async function getSystemHealth() {
  return fetchAPI('/api/system/health');
}

/**
 * Simple health check
 */
export async function getSimpleHealth() {
  return fetchAPI('/api/system/health/simple');
}

/**
 * Get system information
 */
export async function getSystemInfo() {
  return fetchAPI('/api/system/info');
}

/**
 * Get health status of all components
 */
export async function getAllComponents() {
  return fetchAPI('/api/system/components');
}

/**
 * Get health status of a specific component
 * @param {string} componentType - Component type
 */
export async function getComponentHealth(componentType) {
  return fetchAPI(`/api/system/components/${componentType}`);
}

// ============== Activity API ==============

/**
 * Get recent activity feed
 * @param {number} limit - Number of items to return
 */
export async function getRecentActivity(limit = 50) {
  return fetchAPI(`/api/activity/recent?limit=${limit}`);
}

export default {
  // Analytics
  getDashboardOverview,
  getAnalyticsSummary,
  getLogLevelBreakdown,
  getServiceStatistics,
  getServiceDetails,
  getRealTimeStats,
  getTimeSeriesData,
  // Logs
  getRecentLogs,
  getLogStreamInfo,
  triggerLogGeneration,
  // Alerts
  getRecentAlerts,
  getAlert,
  updateAlertStatus,
  getRemediation,
  triggerRemediation,
  // System
  getSystemHealth,
  getSimpleHealth,
  getSystemInfo,
  getAllComponents,
  getComponentHealth,
  // Activity
  getRecentActivity,
};
