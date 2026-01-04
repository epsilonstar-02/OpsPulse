import { LayoutDashboard, Settings, BarChart3, AlertCircle, Server, LogOut } from 'lucide-react'

const menuItems = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'metrics', label: 'Metrics', icon: BarChart3 },
  { id: 'alerts', label: 'Alerts', icon: AlertCircle },
  { id: 'services', label: 'Services', icon: Server },
  { id: 'settings', label: 'Settings', icon: Settings },
]

export default function Sidebar({ isOpen, activeView, onViewChange }) {
  return (
    <aside className={`bg-slate-800 border-r border-slate-700 transition-all duration-300 flex flex-col ${isOpen ? 'w-64' : 'w-20'}`}>
      {/* Logo */}
      <div className="p-4 h-16 flex items-center border-b border-slate-700">
        <div className={`flex items-center gap-3 ${!isOpen && 'justify-center w-full'}`}>
          <div className="w-8 h-8 bg-gradient-to-br from-blue-400 to-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">OP</span>
          </div>
          {isOpen && <span className="font-bold text-white">OpsPulse</span>}
        </div>
      </div>

      {/* Menu Items */}
      <nav className="p-4 space-y-2 flex-1">
        {menuItems.map(item => {
          const Icon = item.icon
          const isActive = activeView === item.id
          return (
            <button
              key={item.id}
              onClick={() => onViewChange(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-700'
              } ${!isOpen && 'justify-center'}`}
            >
              <Icon className="w-5 h-5 shrink-0" />
              {isOpen && <span className="text-sm font-medium">{item.label}</span>}
            </button>
          )
        })}
      </nav>

      {/* Bottom Section */}
      <div className="p-4 border-t border-slate-700">
        <button className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-slate-300 hover:bg-slate-700 transition-colors ${!isOpen && 'justify-center'}`}>
          <LogOut className="w-5 h-5" />
          {isOpen && <span className="text-sm font-medium">Logout</span>}
        </button>
      </div>
    </aside>
  )
}
