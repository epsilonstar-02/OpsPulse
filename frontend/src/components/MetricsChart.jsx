import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { useState, useEffect, useRef } from 'react'
import { useDashboard } from '../context/DashboardContext'

export default function MetricsChart() {
  const { stats, isConnected } = useDashboard()
  const [chartType, setChartType] = useState('line')
  const [data, setData] = useState([])
  const dataRef = useRef([])

  // Initialize with empty data points
  useEffect(() => {
    const initialData = []
    const now = new Date()
    for (let i = 19; i >= 0; i--) {
      const time = new Date(now - i * 5000) // 5 second intervals
      initialData.push({
        time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        logs: 0,
        errors: 0,
        anomalies: 0,
      })
    }
    dataRef.current = initialData
    setData(initialData)
  }, [])

  // Update chart with real-time stats
  useEffect(() => {
    const now = new Date()
    const newPoint = {
      time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
      logs: Math.round((stats.logs_per_second || 0) * 10) / 10,
      errors: Math.round((stats.errors_per_second || 0) * 100) / 10,
      anomalies: Math.round((stats.anomalies_per_second || 0) * 100) / 10,
    }
    
    dataRef.current = [...dataRef.current.slice(1), newPoint]
    setData([...dataRef.current])
  }, [stats])

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 h-96">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-white">Log Metrics</h2>
          {isConnected ? (
            <span className="flex items-center gap-1.5 text-xs text-emerald-400">
              <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
              Live
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs text-amber-400">
              <span className="w-2 h-2 bg-amber-400 rounded-full"></span>
              Offline
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setChartType('line')}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              chartType === 'line'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            Line
          </button>
          <button
            onClick={() => setChartType('area')}
            className={`px-3 py-1 rounded text-sm transition-colors ${
              chartType === 'area'
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            Area
          </button>
        </div>
      </div>

      <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        {chartType === 'line' ? (
          <LineChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
            <YAxis stroke="#94a3b8" fontSize={12} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
              labelStyle={{ color: '#fff' }}
            />
            <Legend />
            <Line type="monotone" dataKey="logs" stroke="#3b82f6" strokeWidth={2} dot={false} name="Logs/s" isAnimationActive={false} />
            <Line type="monotone" dataKey="errors" stroke="#ef4444" strokeWidth={2} dot={false} name="Errors/s (×10)" isAnimationActive={false} />
            <Line type="monotone" dataKey="anomalies" stroke="#f59e0b" strokeWidth={2} dot={false} name="Anomalies/s (×10)" isAnimationActive={false} />
          </LineChart>
        ) : (
          <AreaChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
            <YAxis stroke="#94a3b8" fontSize={12} />
            <Tooltip 
              contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
              labelStyle={{ color: '#fff' }}
            />
            <Legend />
            <Area type="monotone" dataKey="logs" stackId="1" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.4} name="Logs/s" isAnimationActive={false} />
            <Area type="monotone" dataKey="errors" stackId="2" stroke="#ef4444" fill="#ef4444" fillOpacity={0.4} name="Errors/s (×10)" isAnimationActive={false} />
            <Area type="monotone" dataKey="anomalies" stackId="3" stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.4} name="Anomalies/s (×10)" isAnimationActive={false} />
          </AreaChart>
        )}
      </ResponsiveContainer>
      </div>
    </div>
  )
}
