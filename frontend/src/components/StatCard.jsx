export default function StatCard({ title, value, icon, color, trend }) {
  const colorClasses = {
    emerald: 'from-emerald-500/20 to-emerald-600/20 border-emerald-500/30',
    blue: 'from-blue-500/20 to-blue-600/20 border-blue-500/30',
    red: 'from-red-500/20 to-red-600/20 border-red-500/30',
    amber: 'from-amber-500/20 to-amber-600/20 border-amber-500/30',
  }

  const iconColorClasses = {
    emerald: 'text-emerald-400',
    blue: 'text-blue-400',
    red: 'text-red-400',
    amber: 'text-amber-400',
  }

  return (
    <div className={`bg-linear-to-br ${colorClasses[color]} border rounded-lg p-6 backdrop-blur-sm hover:shadow-lg transition-shadow`}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <p className="text-slate-400 text-sm font-medium">{title}</p>
          <p className="text-3xl font-bold text-white mt-2">{value}</p>
        </div>
        <div className={`${iconColorClasses[color]} opacity-80`}>
          {icon}
        </div>
      </div>
      <p className="text-xs text-slate-400">{trend}</p>
    </div>
  )
}
