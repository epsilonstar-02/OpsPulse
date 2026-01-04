import { useState } from 'react'
import Header from './Header'
import Sidebar from './Sidebar'
import DashboardHome from './pages/DashboardHome'
import MetricsPage from './pages/MetricsPage'
import AlertsPage from './pages/AlertsPage'
import ServicesPage from './pages/ServicesPage'
import SettingsPage from './pages/SettingsPage'

export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeView, setActiveView] = useState('dashboard')

  const renderContent = () => {
    switch (activeView) {
      case 'dashboard':
        return <DashboardHome />
      case 'metrics':
        return <MetricsPage />
      case 'alerts':
        return <AlertsPage />
      case 'services':
        return <ServicesPage />
      case 'settings':
        return <SettingsPage />
      default:
        return <DashboardHome />
    }
  }

  return (
    <div className="flex h-screen bg-slate-900">
      {/* Sidebar */}
      <Sidebar 
        isOpen={sidebarOpen} 
        activeView={activeView}
        onViewChange={setActiveView}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <Header onMenuClick={() => setSidebarOpen(!sidebarOpen)} />

        {/* Main Dashboard Content */}
        <main className="flex-1 overflow-auto">
          {renderContent()}
        </main>
      </div>
    </div>
  )
}
