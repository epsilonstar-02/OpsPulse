import { X, AlertTriangle, AlertCircle } from 'lucide-react'

export default function AlertsList({ alerts, onDismiss }) {
  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-500/20 border-red-500/30 text-red-300'
      case 'warning':
        return 'bg-amber-500/20 border-amber-500/30 text-amber-300'
      default:
        return 'bg-blue-500/20 border-blue-500/30 text-blue-300'
    }
  }

  const getIcon = (severity) => {
    return severity === 'critical' ? (
      <AlertTriangle className="w-5 h-5" />
    ) : (
      <AlertCircle className="w-5 h-5" />
    )
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 h-96 overflow-y-auto">
      <h2 className="text-lg font-semibold text-white mb-4">Recent Alerts</h2>

      {alerts.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-slate-400 text-sm">No alerts at the moment</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map(alert => (
            <div
              key={alert.id}
              className={`border rounded-lg p-4 ${getSeverityColor(alert.severity)} flex items-start justify-between gap-3`}
            >
              <div className="flex items-start gap-3 flex-1">
                {getIcon(alert.severity)}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm">{alert.title}</p>
                  <p className="text-xs opacity-80">{alert.service}</p>
                  <p className="text-xs opacity-60 mt-1">{alert.time}</p>
                </div>
              </div>
              <button
                onClick={() => onDismiss(alert.id)}
                className="shrink-0 p-1 hover:bg-white/10 rounded transition-colors"
                aria-label="Dismiss alert"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
