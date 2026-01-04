import { useState, useEffect } from 'react'
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Cpu, HardDrive, Wifi, Clock } from 'lucide-react'

export default function MetricsPage() {
  const [timeRange, setTimeRange] = useState('1h')
  const [metricsData, setMetricsData] = useState([])
  const [liveStats, setLiveStats] = useState({
    cpu: 45,
    memory: 62,
    disk: 78,
    network: 156
  })

  // Generate initial data
  useEffect(() => {
    const generateData = () => {
      const data = []
      const now = new Date()
      for (let i = 20; i >= 0; i--) {
        const time = new Date(now - i * 3 * 60000)
        data.push({
          time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
          cpu: Math.floor(30 + Math.random() * 50),
          memory: Math.floor(40 + Math.random() * 40),
          disk: Math.floor(60 + Math.random() * 30),
          network: Math.floor(100 + Math.random() * 200)
        })
      }
      return data
    }
    setMetricsData(generateData())
  }, [])

  // Real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date()
      const newCpu = Math.max(10, Math.min(95, liveStats.cpu + (Math.random() - 0.5) * 15))
      const newMemory = Math.max(20, Math.min(90, liveStats.memory + (Math.random() - 0.5) * 10))
      const newDisk = Math.max(50, Math.min(95, liveStats.disk + (Math.random() - 0.5) * 5))
      const newNetwork = Math.max(50, Math.min(400, liveStats.network + (Math.random() - 0.5) * 50))

      setLiveStats({
        cpu: newCpu,
        memory: newMemory,
        disk: newDisk,
        network: newNetwork
      })

      setMetricsData(prev => {
        const newData = [...prev.slice(1), {
          time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
          cpu: Math.floor(newCpu),
          memory: Math.floor(newMemory),
          disk: Math.floor(newDisk),
          network: Math.floor(newNetwork)
        }]
        return newData
      })
    }, 2000)

    return () => clearInterval(interval)
  }, [liveStats])

  const metricCards = [
    { label: 'CPU Usage', value: `${Math.round(liveStats.cpu)}%`, icon: Cpu, color: 'blue', max: 100 },
    { label: 'Memory', value: `${Math.round(liveStats.memory)}%`, icon: HardDrive, color: 'purple', max: 100 },
    { label: 'Disk I/O', value: `${Math.round(liveStats.disk)}%`, icon: HardDrive, color: 'emerald', max: 100 },
    { label: 'Network', value: `${Math.round(liveStats.network)} Mbps`, icon: Wifi, color: 'amber', max: 500 }
  ]

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">System Metrics</h1>
          <p className="text-slate-400 mt-1">Real-time performance monitoring</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-2 text-emerald-400 text-sm">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></span>
            Live
          </span>
          <select 
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2 text-sm"
          >
            <option value="1h">Last 1 hour</option>
            <option value="6h">Last 6 hours</option>
            <option value="24h">Last 24 hours</option>
            <option value="7d">Last 7 days</option>
          </select>
        </div>
      </div>

      {/* Live Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        {metricCards.map((metric, index) => {
          const Icon = metric.icon
          const percentage = metric.label === 'Network' ? (liveStats.network / 500) * 100 : 
                            metric.label === 'CPU Usage' ? liveStats.cpu :
                            metric.label === 'Memory' ? liveStats.memory : liveStats.disk
          return (
            <div key={index} className="bg-slate-800 border border-slate-700 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <div className={`p-2 rounded-lg bg-${metric.color}-500/20`}>
                  <Icon className={`w-5 h-5 text-${metric.color}-400`} />
                </div>
                <span className="text-xs text-slate-400 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> Just now
                </span>
              </div>
              <p className="text-slate-400 text-sm">{metric.label}</p>
              <p className="text-2xl font-bold text-white mt-1">{metric.value}</p>
              <div className="mt-4 h-2 bg-slate-700 rounded-full overflow-hidden">
                <div 
                  className={`h-full bg-${metric.color}-500 transition-all duration-500`}
                  style={{ width: `${Math.min(100, percentage)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* CPU & Memory Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">CPU & Memory Usage</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={metricsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} domain={[0, 100]} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                  labelStyle={{ color: '#fff' }}
                />
                <Legend />
                <Area type="monotone" dataKey="cpu" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} name="CPU %" />
                <Area type="monotone" dataKey="memory" stroke="#a855f7" fill="#a855f7" fillOpacity={0.3} name="Memory %" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Network Throughput</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={metricsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                  labelStyle={{ color: '#fff' }}
                />
                <Legend />
                <Line type="monotone" dataKey="network" stroke="#f59e0b" strokeWidth={2} dot={false} name="Network Mbps" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Disk Usage */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-white mb-4">Disk I/O Over Time</h3>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={metricsData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
              <YAxis stroke="#94a3b8" fontSize={12} domain={[0, 100]} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                labelStyle={{ color: '#fff' }}
              />
              <Legend />
              <Bar dataKey="disk" fill="#10b981" name="Disk I/O %" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
