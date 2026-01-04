import { Menu, Bell, User, Settings, Wifi, WifiOff } from 'lucide-react'
import { useDashboard } from '../context/DashboardContext'

export default function Header({ onMenuClick }) {
  const { isConnected, connectionState, overview, alerts } = useDashboard()
  
  // Count active alerts for the notification badge
  const activeAlerts = alerts?.filter(a => a.status === 'active')?.length || 0

  return (
    <header className="bg-slate-800 border-b border-slate-700 h-16 flex items-center justify-between px-8">
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          aria-label="Toggle menu"
        >
          <Menu className="w-6 h-6 text-slate-300" />
        </button>
        <h1 className="text-xl font-bold text-white">OpsPulse Dashboard</h1>
        
        {/* Pipeline Status Badge */}
        {overview?.pipeline_status && (
          <span className={`px-2 py-1 text-xs rounded-full ${
            overview.pipeline_status === 'running' 
              ? 'bg-emerald-500/20 text-emerald-400' 
              : 'bg-amber-500/20 text-amber-400'
          }`}>
            {overview.pipeline_status}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        {/* Connection Status */}
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${
          isConnected 
            ? 'bg-emerald-500/10 text-emerald-400' 
            : 'bg-red-500/10 text-red-400'
        }`}>
          {isConnected ? (
            <>
              <Wifi className="w-4 h-4" />
              <span className="hidden sm:inline">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="w-4 h-4" />
              <span className="hidden sm:inline">{connectionState}</span>
            </>
          )}
        </div>
        
        <button className="relative p-2 hover:bg-slate-700 rounded-lg transition-colors">
          <Bell className="w-6 h-6 text-slate-300" />
          {activeAlerts > 0 && (
            <span className="absolute -top-1 -right-1 min-w-5 h-5 flex items-center justify-center bg-red-500 text-white text-xs font-bold rounded-full px-1">
              {activeAlerts > 99 ? '99+' : activeAlerts}
            </span>
          )}
        </button>
        <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors">
          <Settings className="w-6 h-6 text-slate-300" />
        </button>
        <button className="p-2 hover:bg-slate-700 rounded-lg transition-colors">
          <User className="w-6 h-6 text-slate-300" />
        </button>
      </div>
    </header>
  )
}
