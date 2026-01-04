import { useMemo } from 'react'
import { useDashboard } from '../../context/DashboardContext'
import StatCard from '../StatCard'
import MetricsChart from '../MetricsChart'
import AlertsList from '../AlertsList'
import SystemHealth from '../SystemHealth'
import { Activity, AlertTriangle, CheckCircle, TrendingUp, Wifi, WifiOff } from 'lucide-react'

export default function DashboardHome() {
  const { 
    overview, 
    stats, 
    alerts, 
    isLoading, 
    isConnected,
    connectionState,
  } = useDashboard()

  // Compute stats from overview data
  const computedStats = useMemo(() => ({
    uptime: overview.pipeline_status === 'running' ? 99.9 : 0,
    incidents: overview.total_alerts || 0,
    activeServices: overview.services_count || 0,
    avgLatency: stats.logs_per_second > 0 ? Math.round(1000 / stats.logs_per_second) : 0,
    logsPerSecond: stats.logs_per_second || 0,
    errorsPerSecond: stats.errors_per_second || 0,
    anomaliesPerSecond: stats.anomalies_per_second || 0,
  }), [overview, stats])

  // Transform alerts for AlertsList component
  const transformedAlerts = useMemo(() => {
    return alerts.slice(0, 5).map((alert, index) => ({
      id: alert.id || index,
      title: alert.title || alert.alert_type || 'Alert',
      severity: alert.severity || 'warning',
      service: alert.service || 'Unknown',
      time: alert.time || 'Just now',
    }))
  }, [alerts])

  const dismissAlert = (id) => {
    // This could be connected to API to actually dismiss alerts
    console.log('Dismiss alert:', id)
  }

  if (isLoading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="flex items-center justify-center h-64">
          <div className="text-slate-400">Loading dashboard data...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard Overview</h1>
          <p className="text-slate-400 mt-1">Welcome back! Here's what's happening with your systems.</p>
        </div>
        
        {/* Connection Status */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
          isConnected 
            ? 'bg-emerald-500/20 text-emerald-400' 
            : 'bg-red-500/20 text-red-400'
        }`}>
          {isConnected ? (
            <>
              <Wifi className="w-4 h-4" />
              <span>Live</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4" />
              <span>{connectionState}</span>
            </>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Pipeline Status"
          value={overview.pipeline_status === 'running' ? 'Running' : overview.pipeline_status}
          icon={<CheckCircle className="w-8 h-8" />}
          color={overview.pipeline_status === 'running' ? 'emerald' : 'red'}
          trend={overview.kafka_connected ? 'Kafka connected' : 'Kafka disconnected'}
        />
        <StatCard
          title="Active Services"
          value={computedStats.activeServices}
          icon={<Activity className="w-8 h-8" />}
          color="blue"
          trend={`${stats.logs_per_second.toFixed(1)} logs/s`}
        />
        <StatCard
          title="Total Alerts"
          value={computedStats.incidents}
          icon={<AlertTriangle className="w-8 h-8" />}
          color="red"
          trend={`${overview.total_anomalies || 0} anomalies detected`}
        />
        <StatCard
          title="Total Logs"
          value={formatNumber(overview.total_logs)}
          icon={<TrendingUp className="w-8 h-8" />}
          color="amber"
          trend={`${overview.logs_per_minute.toFixed(1)} logs/min`}
        />
      </div>

      {/* Charts and Alerts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2">
          <MetricsChart />
        </div>
        <div>
          <AlertsList 
            alerts={transformedAlerts} 
            onDismiss={dismissAlert} 
          />
        </div>
      </div>

      {/* System Health */}
      <SystemHealth />
    </div>
  )
}

/**
 * Format large numbers for display
 */
function formatNumber(num) {
  if (!num) return '0'
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toString()
}
