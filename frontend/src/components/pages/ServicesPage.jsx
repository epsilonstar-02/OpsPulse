import { useState, useEffect } from 'react'
import { useDashboard } from '../../context/DashboardContext'
import { CheckCircle, AlertCircle, XCircle, RefreshCw, Server, Activity, Clock, ArrowUpRight, ArrowDownRight } from 'lucide-react'

export default function ServicesPage() {
  const { services: backendServices, servicesLoading, fetchServices } = useDashboard()
  const [services, setServices] = useState([])
  const [selectedService, setSelectedService] = useState(null)
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Sync services from context or use defaults
  useEffect(() => {
    if (backendServices && backendServices.length > 0) {
      setServices(backendServices.map((service, index) => ({
        id: service.id || index + 1,
        name: service.name || service.service_name || `Service ${index + 1}`,
        status: service.status || getServiceStatus(service),
        uptime: service.uptime || 99.9,
        responseTime: service.responseTime || service.avg_response_time_ms || 100,
        requests: service.requests || service.total_logs || 0,
        cpu: service.cpu || Math.floor(30 + Math.random() * 40),
        memory: service.memory || Math.floor(40 + Math.random() * 40),
        lastCheck: service.lastCheck || 'Just now',
        errorCount: service.errorCount || service.error_count || 0,
        anomalyCount: service.anomalyCount || service.anomaly_count || 0,
      })))
    } else {
      // Use default mock data if no backend data
      setServices(initialServices)
    }
  }, [backendServices])

  // Simulate real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setServices(prev => prev.map(service => ({
        ...service,
        responseTime: Math.max(1, service.responseTime + (Math.random() - 0.5) * 10),
        requests: service.requests + Math.floor(Math.random() * 100),
        cpu: Math.max(10, Math.min(95, service.cpu + (Math.random() - 0.5) * 8)),
        memory: Math.max(20, Math.min(95, service.memory + (Math.random() - 0.5) * 5)),
      })))
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  const refreshServices = async () => {
    setIsRefreshing(true)
    await fetchServices()
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-5 h-5 text-emerald-400" />
      case 'warning': return <AlertCircle className="w-5 h-5 text-amber-400" />
      case 'critical': return <XCircle className="w-5 h-5 text-red-400" />
      default: return <Server className="w-5 h-5 text-slate-400" />
    }
  }

  const getStatusBg = (status) => {
    switch (status) {
      case 'healthy': return 'border-emerald-500/30 hover:border-emerald-500/50'
      case 'warning': return 'border-amber-500/30 hover:border-amber-500/50'
      case 'critical': return 'border-red-500/30 hover:border-red-500/50'
      default: return 'border-slate-500/30'
    }
  }

  const statusCounts = {
    healthy: services.filter(s => s.status === 'healthy').length,
    warning: services.filter(s => s.status === 'warning').length,
    critical: services.filter(s => s.status === 'critical').length,
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Services</h1>
          <p className="text-slate-400 mt-1">Monitor all running services</p>
        </div>
        <button
          onClick={refreshServices}
          className={`flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors ${isRefreshing ? 'opacity-50' : ''}`}
          disabled={isRefreshing}
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Status Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4 flex items-center gap-4">
          <div className="p-3 bg-emerald-500/20 rounded-lg">
            <CheckCircle className="w-6 h-6 text-emerald-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-white">{statusCounts.healthy}</p>
            <p className="text-sm text-emerald-400">Healthy Services</p>
          </div>
        </div>
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 flex items-center gap-4">
          <div className="p-3 bg-amber-500/20 rounded-lg">
            <AlertCircle className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-white">{statusCounts.warning}</p>
            <p className="text-sm text-amber-400">Warnings</p>
          </div>
        </div>
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center gap-4">
          <div className="p-3 bg-red-500/20 rounded-lg">
            <XCircle className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <p className="text-2xl font-bold text-white">{statusCounts.critical}</p>
            <p className="text-sm text-red-400">Critical</p>
          </div>
        </div>
      </div>

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map((service) => (
          <div
            key={service.id}
            onClick={() => setSelectedService(selectedService?.id === service.id ? null : service)}
            className={`bg-slate-800 border rounded-lg p-4 cursor-pointer transition-all ${getStatusBg(service.status)} ${
              selectedService?.id === service.id ? 'ring-2 ring-blue-500' : ''
            }`}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                {getStatusIcon(service.status)}
                <div>
                  <h3 className="font-medium text-white">{service.name}</h3>
                  <p className="text-xs text-slate-400">{service.lastCheck}</p>
                </div>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full ${
                service.status === 'healthy' ? 'bg-emerald-500/20 text-emerald-400' :
                service.status === 'warning' ? 'bg-amber-500/20 text-amber-400' :
                'bg-red-500/20 text-red-400'
              }`}>
                {service.uptime.toFixed(2)}% uptime
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Response
                </p>
                <p className="text-white font-medium flex items-center gap-1">
                  {Math.round(service.responseTime)}ms
                  {service.responseTime < 100 ? (
                    <ArrowDownRight className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <ArrowUpRight className="w-3 h-3 text-red-400" />
                  )}
                </p>
              </div>
              <div>
                <p className="text-slate-400 flex items-center gap-1">
                  <Activity className="w-3 h-3" /> Requests
                </p>
                <p className="text-white font-medium">{(service.requests / 1000).toFixed(1)}K</p>
              </div>
            </div>

            {/* CPU & Memory bars */}
            <div className="mt-4 space-y-2">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">CPU</span>
                  <span className={`${service.cpu > 80 ? 'text-red-400' : 'text-slate-300'}`}>{Math.round(service.cpu)}%</span>
                </div>
                <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 ${service.cpu > 80 ? 'bg-red-500' : service.cpu > 60 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                    style={{ width: `${service.cpu}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">Memory</span>
                  <span className={`${service.memory > 80 ? 'text-red-400' : 'text-slate-300'}`}>{Math.round(service.memory)}%</span>
                </div>
                <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 ${service.memory > 80 ? 'bg-red-500' : service.memory > 60 ? 'bg-amber-500' : 'bg-blue-500'}`}
                    style={{ width: `${service.memory}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Helper function to determine service status from error/anomaly rates
 */
function getServiceStatus(service) {
  const errorRate = service.error_rate || 0
  const anomalyCount = service.anomaly_count || 0
  
  if (errorRate > 0.1) return 'critical'
  if (errorRate > 0.05 || anomalyCount > 5) return 'warning'
  return 'healthy'
}

/**
 * Default services for when backend is unavailable
 */
const initialServices = [
  { id: 1, name: 'API Server', status: 'healthy', uptime: 99.99, responseTime: 45, requests: 15234, cpu: 45, memory: 62, lastCheck: 'Just now' },
  { id: 2, name: 'Database Primary', status: 'healthy', uptime: 99.95, responseTime: 12, requests: 8521, cpu: 38, memory: 71, lastCheck: '10s ago' },
  { id: 3, name: 'Cache Service', status: 'warning', uptime: 98.50, responseTime: 8, requests: 45123, cpu: 78, memory: 82, lastCheck: '5s ago' },
  { id: 4, name: 'Load Balancer', status: 'healthy', uptime: 100, responseTime: 2, requests: 125000, cpu: 22, memory: 35, lastCheck: 'Just now' },
  { id: 5, name: 'Message Queue', status: 'healthy', uptime: 99.85, responseTime: 25, requests: 8900, cpu: 42, memory: 58, lastCheck: '15s ago' },
  { id: 6, name: 'Auth Service', status: 'healthy', uptime: 99.98, responseTime: 32, requests: 6700, cpu: 28, memory: 42, lastCheck: '5s ago' },
]
