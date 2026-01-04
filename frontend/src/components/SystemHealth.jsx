import { useState, useEffect } from 'react'
import { useDashboard } from '../context/DashboardContext'
import { CheckCircle, AlertCircle, XCircle, Clock, RefreshCw } from 'lucide-react'

export default function SystemHealth() {
  const { systemHealth, services: backendServices, healthLoading, fetchSystemHealth } = useDashboard()
  const [services, setServices] = useState([])
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Build services list from system health or backend services
  useEffect(() => {
    if (systemHealth?.components) {
      // Use component health data
      setServices(systemHealth.components.map((comp, index) => ({
        id: index + 1,
        name: comp.name,
        status: comp.status === 'healthy' ? 'healthy' : comp.status === 'degraded' ? 'warning' : 'critical',
        uptime: comp.uptime || '99.9%',
        responseTime: `${comp.response_time_ms || 0}ms`,
        requests: comp.requests_per_sec ? `${comp.requests_per_sec}/s` : 'N/A',
      })))
    } else if (backendServices && backendServices.length > 0) {
      // Fall back to services data
      setServices(backendServices.slice(0, 6).map((service, index) => ({
        id: index + 1,
        name: service.name || service.service_name,
        status: service.status || 'healthy',
        uptime: `${(service.uptime || 99.9).toFixed(1)}%`,
        responseTime: `${Math.round(service.responseTime || service.avg_response_time_ms || 100)}ms`,
        requests: service.requests ? `${(service.requests / 1000).toFixed(1)}K/s` : 'N/A',
      })))
    } else {
      // Use default data
      setServices(defaultServices)
    }
  }, [systemHealth, backendServices])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    await fetchSystemHealth()
    setIsRefreshing(false)
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-emerald-400" />
      case 'warning':
      case 'degraded':
        return <AlertCircle className="w-5 h-5 text-amber-400" />
      case 'critical':
      case 'unhealthy':
        return <XCircle className="w-5 h-5 text-red-400" />
      default:
        return <AlertCircle className="w-5 h-5 text-slate-400" />
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':
        return 'bg-emerald-500/20 border-emerald-500/30'
      case 'warning':
      case 'degraded':
        return 'bg-amber-500/20 border-amber-500/30'
      case 'critical':
      case 'unhealthy':
        return 'bg-red-500/20 border-red-500/30'
      default:
        return 'bg-slate-500/20 border-slate-500/30'
    }
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-white">Services Health</h2>
        <button
          onClick={handleRefresh}
          className={`p-2 rounded-lg hover:bg-slate-700 transition-colors ${isRefreshing ? 'opacity-50' : ''}`}
          disabled={isRefreshing}
        >
          <RefreshCw className={`w-4 h-4 text-slate-400 ${isRefreshing ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {healthLoading && services.length === 0 ? (
        <div className="text-center py-8 text-slate-400">Loading health data...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {services.map(service => (
            <div
              key={service.id}
              className={`border rounded-lg p-4 ${getStatusColor(service.status)} transition-all hover:shadow-lg`}
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-white">{service.name}</h3>
                </div>
                {getStatusIcon(service.status)}
              </div>

              <div className="space-y-2 text-xs text-slate-300">
                <div className="flex items-center justify-between">
                  <span>Uptime:</span>
                  <span className="font-medium text-white">{service.uptime}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Response:
                  </span>
                  <span className="font-medium text-white">{service.responseTime}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span>Requests:</span>
                  <span className="font-medium text-white">{service.requests}</span>
                </div>
              </div>

              {/* Progress bar */}
              <div className="mt-4 h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full ${service.status === 'healthy' ? 'bg-emerald-400' : service.status === 'warning' ? 'bg-amber-400' : 'bg-red-400'}`}
                  style={{ width: service.status === 'healthy' ? '100%' : service.status === 'warning' ? '85%' : '50%' }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Default services for when backend is unavailable
 */
const defaultServices = [
  { id: 1, name: 'API Server', status: 'healthy', uptime: '99.9%', responseTime: '120ms', requests: '15.2K/s' },
  { id: 2, name: 'Database', status: 'healthy', uptime: '99.8%', responseTime: '85ms', requests: '8.5K/s' },
  { id: 3, name: 'Cache Service', status: 'warning', uptime: '98.5%', responseTime: '45ms', requests: '12.3K/s' },
  { id: 4, name: 'Load Balancer', status: 'healthy', uptime: '100%', responseTime: '5ms', requests: '25.7K/s' },
  { id: 5, name: 'Message Queue', status: 'healthy', uptime: '99.7%', responseTime: '65ms', requests: '5.2K/s' },
  { id: 6, name: 'Search Engine', status: 'healthy', uptime: '99.5%', responseTime: '150ms', requests: '3.1K/s' },
]
