import Dashboard from './components/Dashboard'
import { DashboardProvider } from './context/DashboardContext'
import './App.css'

function App() {
  return (
    <DashboardProvider>
      <div className="min-h-screen bg-slate-900">
        <Dashboard />
      </div>
    </DashboardProvider>
  )
}

export default App
