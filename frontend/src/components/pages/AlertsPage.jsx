import { useState, useEffect, useMemo } from 'react'
import { useDashboard } from '../../context/DashboardContext'
import { AlertTriangle, AlertCircle, Info, X, CheckCircle, Filter, Search, Bell, RefreshCw } from 'lucide-react'
import * as api from '../../services/api'

export default function AlertsPage() {
  const { alerts: realtimeAlerts, alertsLoading, fetchAlerts } = useDashboard()
  const [alerts, setAlerts] = useState([])
  const [filter, setFilter] = useState('all')
  const [severityFilter, setSeverityFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Sync alerts from context
  useEffect(() => {
    if (realtimeAlerts && realtimeAlerts.length > 0) {
      setAlerts(realtimeAlerts.map((alert, index) => ({
        id: alert.id || index + 1,
        title: alert.title || alert.alert_type || 'Alert',
        description: alert.description || alert.message || `${alert.alert_type || 'Issue'} detected on ${alert.service || 'system'}`,
        severity: alert.severity || 'warning',
        service: alert.service || 'Unknown',
        time: alert.time || formatTimestamp(alert.timestamp),
        status: alert.status || 'active',
      })))
    }
  }, [realtimeAlerts])

  const handleRefresh = async () => {
    setIsRefreshing(true)
    await fetchAlerts()
    setIsRefreshing(false)
  }

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return <AlertTriangle className="w-5 h-5 text-red-400" />
      case 'warning': return <AlertCircle className="w-5 h-5 text-amber-400" />
      case 'info': return <Info className="w-5 h-5 text-blue-400" />
      default: return <Bell className="w-5 h-5 text-slate-400" />
    }
  }

  const getSeverityBg = (severity) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/10 border-red-500/30'
      case 'warning': return 'bg-amber-500/10 border-amber-500/30'
      case 'info': return 'bg-blue-500/10 border-blue-500/30'
      default: return 'bg-slate-500/10 border-slate-500/30'
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'active': return <span className="px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400">Active</span>
      case 'acknowledged': return <span className="px-2 py-1 text-xs rounded-full bg-amber-500/20 text-amber-400">Acknowledged</span>
      case 'resolved': return <span className="px-2 py-1 text-xs rounded-full bg-emerald-500/20 text-emerald-400">Resolved</span>
      default: return null
    }
  }

  const acknowledgeAlert = (id) => {
    setAlerts(alerts.map(alert => 
      alert.id === id ? { ...alert, status: 'acknowledged' } : alert
    ))
  }

  const resolveAlert = (id) => {
    setAlerts(alerts.map(alert => 
      alert.id === id ? { ...alert, status: 'resolved' } : alert
    ))
  }

  const dismissAlert = (id) => {
    setAlerts(alerts.filter(alert => alert.id !== id))
  }

  const filteredAlerts = alerts.filter(alert => {
    const matchesStatus = filter === 'all' || alert.status === filter
    const matchesSeverity = severityFilter === 'all' || alert.severity === severityFilter
    const matchesSearch = alert.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         alert.service.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesStatus && matchesSeverity && matchesSearch
  })

  const alertCounts = {
    all: alerts.length,
    active: alerts.filter(a => a.status === 'active').length,
    acknowledged: alerts.filter(a => a.status === 'acknowledged').length,
    resolved: alerts.filter(a => a.status === 'resolved').length,
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Alerts</h1>
          <p className="text-slate-400 mt-1">Monitor and manage system alerts</p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={handleRefresh}
            className={`flex items-center gap-2 px-3 py-1.5 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors text-sm ${isRefreshing ? 'opacity-50' : ''}`}
            disabled={isRefreshing}
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <span className="flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/20 text-red-400 text-sm">
            <span className="w-2 h-2 bg-red-400 rounded-full animate-pulse"></span>
            {alertCounts.active} Active
          </span>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 mb-6">
        <div className="flex flex-wrap items-center gap-4">
          {/* Search */}
          <div className="relative flex-1 min-w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search alerts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <div className="flex rounded-lg overflow-hidden border border-slate-600">
              {['all', 'active', 'acknowledged', 'resolved'].map((status) => (
                <button
                  key={status}
                  onClick={() => setFilter(status)}
                  className={`px-3 py-1.5 text-sm capitalize transition-colors ${
                    filter === status
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                  }`}
                >
                  {status} ({alertCounts[status]})
                </button>
              ))}
            </div>
          </div>

          {/* Severity Filter */}
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>
      </div>

      {/* Alerts List */}
      <div className="space-y-4">
        {filteredAlerts.length === 0 ? (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-12 text-center">
            <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
            <p className="text-lg font-medium text-white">No alerts found</p>
            <p className="text-slate-400 mt-1">All systems operating normally</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => (
            <div
              key={alert.id}
              className={`border rounded-lg p-4 ${getSeverityBg(alert.severity)} transition-all hover:shadow-lg`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4 flex-1">
                  <div className="mt-1">{getSeverityIcon(alert.severity)}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-medium text-white">{alert.title}</h3>
                      {getStatusBadge(alert.status)}
                    </div>
                    <p className="text-sm text-slate-400 mb-2">{alert.description}</p>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span className="px-2 py-0.5 rounded bg-slate-700">{alert.service}</span>
                      <span>{alert.time}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {alert.status === 'active' && (
                    <>
                      <button
                        onClick={() => acknowledgeAlert(alert.id)}
                        className="px-3 py-1.5 text-xs rounded bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-colors"
                      >
                        Acknowledge
                      </button>
                      <button
                        onClick={() => resolveAlert(alert.id)}
                        className="px-3 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors"
                      >
                        Resolve
                      </button>
                    </>
                  )}
                  {alert.status === 'acknowledged' && (
                    <button
                      onClick={() => resolveAlert(alert.id)}
                      className="px-3 py-1.5 text-xs rounded bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors"
                    >
                      Resolve
                    </button>
                  )}
                  <button
                    onClick={() => dismissAlert(alert.id)}
                    className="p-1.5 rounded hover:bg-white/10 transition-colors"
                  >
                    <X className="w-4 h-4 text-slate-400" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

/**
 * Format timestamp as relative time
 */
function formatTimestamp(timestamp) {
  if (!timestamp) return 'Just now'
  
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  
  if (diffSec < 60) return 'Just now'
  if (diffMin < 60) return `${diffMin} min${diffMin > 1 ? 's' : ''} ago`
  if (diffHour < 24) return `${diffHour} hour${diffHour > 1 ? 's' : ''} ago`
  return date.toLocaleDateString()
}
