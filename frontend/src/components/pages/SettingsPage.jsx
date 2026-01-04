import { useState } from 'react'
import { Bell, Moon, Sun, Globe, Shield, Mail, Smartphone, Save, User, Key, Database, Trash2 } from 'lucide-react'

export default function SettingsPage() {
  const [settings, setSettings] = useState({
    darkMode: true,
    notifications: true,
    emailAlerts: true,
    smsAlerts: false,
    criticalOnly: false,
    autoRefresh: true,
    refreshInterval: 30,
    timezone: 'UTC',
    language: 'en',
    twoFactor: false,
  })

  const [activeTab, setActiveTab] = useState('general')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const tabs = [
    { id: 'general', label: 'General', icon: Sun },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'security', label: 'Security', icon: Shield },
    { id: 'account', label: 'Account', icon: User },
  ]

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Settings</h1>
          <p className="text-slate-400 mt-1">Manage your preferences and account</p>
        </div>
        <button
          onClick={handleSave}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
            saved ? 'bg-emerald-600 text-white' : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          <Save className="w-4 h-4" />
          {saved ? 'Saved!' : 'Save Changes'}
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-8 border-b border-slate-700 pb-4">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-white'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* General Settings */}
      {activeTab === 'general' && (
        <div className="space-y-6">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Appearance</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {settings.darkMode ? <Moon className="w-5 h-5 text-blue-400" /> : <Sun className="w-5 h-5 text-amber-400" />}
                  <div>
                    <p className="text-white font-medium">Dark Mode</p>
                    <p className="text-sm text-slate-400">Use dark theme for the dashboard</p>
                  </div>
                </div>
                <button
                  onClick={() => setSettings({ ...settings, darkMode: !settings.darkMode })}
                  className={`w-12 h-6 rounded-full transition-colors ${settings.darkMode ? 'bg-blue-600' : 'bg-slate-600'}`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.darkMode ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Data Refresh</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-white font-medium">Auto Refresh</p>
                  <p className="text-sm text-slate-400">Automatically refresh dashboard data</p>
                </div>
                <button
                  onClick={() => setSettings({ ...settings, autoRefresh: !settings.autoRefresh })}
                  className={`w-12 h-6 rounded-full transition-colors ${settings.autoRefresh ? 'bg-blue-600' : 'bg-slate-600'}`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.autoRefresh ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>
              {settings.autoRefresh && (
                <div>
                  <label className="text-sm text-slate-400 block mb-2">Refresh Interval (seconds)</label>
                  <input
                    type="range"
                    min="5"
                    max="60"
                    value={settings.refreshInterval}
                    onChange={(e) => setSettings({ ...settings, refreshInterval: Number(e.target.value) })}
                    className="w-full accent-blue-600"
                  />
                  <div className="flex justify-between text-xs text-slate-500">
                    <span>5s</span>
                    <span className="text-blue-400">{settings.refreshInterval}s</span>
                    <span>60s</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Localization</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-slate-400 block mb-2">Timezone</label>
                <select
                  value={settings.timezone}
                  onChange={(e) => setSettings({ ...settings, timezone: e.target.value })}
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2"
                >
                  <option value="UTC">UTC</option>
                  <option value="EST">Eastern Time (EST)</option>
                  <option value="PST">Pacific Time (PST)</option>
                  <option value="IST">India Standard Time (IST)</option>
                  <option value="GMT">Greenwich Mean Time (GMT)</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-slate-400 block mb-2">Language</label>
                <select
                  value={settings.language}
                  onChange={(e) => setSettings({ ...settings, language: e.target.value })}
                  className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2"
                >
                  <option value="en">English</option>
                  <option value="es">Spanish</option>
                  <option value="fr">French</option>
                  <option value="de">German</option>
                  <option value="ja">Japanese</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Notifications Settings */}
      {activeTab === 'notifications' && (
        <div className="space-y-6">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Alert Channels</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Bell className="w-5 h-5 text-blue-400" />
                  <div>
                    <p className="text-white font-medium">Push Notifications</p>
                    <p className="text-sm text-slate-400">Receive in-app notifications</p>
                  </div>
                </div>
                <button
                  onClick={() => setSettings({ ...settings, notifications: !settings.notifications })}
                  className={`w-12 h-6 rounded-full transition-colors ${settings.notifications ? 'bg-blue-600' : 'bg-slate-600'}`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.notifications ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Mail className="w-5 h-5 text-emerald-400" />
                  <div>
                    <p className="text-white font-medium">Email Alerts</p>
                    <p className="text-sm text-slate-400">Receive alerts via email</p>
                  </div>
                </div>
                <button
                  onClick={() => setSettings({ ...settings, emailAlerts: !settings.emailAlerts })}
                  className={`w-12 h-6 rounded-full transition-colors ${settings.emailAlerts ? 'bg-blue-600' : 'bg-slate-600'}`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.emailAlerts ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Smartphone className="w-5 h-5 text-purple-400" />
                  <div>
                    <p className="text-white font-medium">SMS Alerts</p>
                    <p className="text-sm text-slate-400">Receive alerts via SMS</p>
                  </div>
                </div>
                <button
                  onClick={() => setSettings({ ...settings, smsAlerts: !settings.smsAlerts })}
                  className={`w-12 h-6 rounded-full transition-colors ${settings.smsAlerts ? 'bg-blue-600' : 'bg-slate-600'}`}
                >
                  <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.smsAlerts ? 'translate-x-6' : 'translate-x-0.5'}`} />
                </button>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Alert Preferences</h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-white font-medium">Critical Alerts Only</p>
                <p className="text-sm text-slate-400">Only receive critical severity alerts</p>
              </div>
              <button
                onClick={() => setSettings({ ...settings, criticalOnly: !settings.criticalOnly })}
                className={`w-12 h-6 rounded-full transition-colors ${settings.criticalOnly ? 'bg-blue-600' : 'bg-slate-600'}`}
              >
                <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.criticalOnly ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Security Settings */}
      {activeTab === 'security' && (
        <div className="space-y-6">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Two-Factor Authentication</h3>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Shield className="w-5 h-5 text-emerald-400" />
                <div>
                  <p className="text-white font-medium">Enable 2FA</p>
                  <p className="text-sm text-slate-400">Add an extra layer of security</p>
                </div>
              </div>
              <button
                onClick={() => setSettings({ ...settings, twoFactor: !settings.twoFactor })}
                className={`w-12 h-6 rounded-full transition-colors ${settings.twoFactor ? 'bg-blue-600' : 'bg-slate-600'}`}
              >
                <div className={`w-5 h-5 bg-white rounded-full transition-transform ${settings.twoFactor ? 'translate-x-6' : 'translate-x-0.5'}`} />
              </button>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Change Password</h3>
            <div className="space-y-4">
              <div>
                <label className="text-sm text-slate-400 block mb-2">Current Password</label>
                <input type="password" className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2" placeholder="••••••••" />
              </div>
              <div>
                <label className="text-sm text-slate-400 block mb-2">New Password</label>
                <input type="password" className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2" placeholder="••••••••" />
              </div>
              <div>
                <label className="text-sm text-slate-400 block mb-2">Confirm New Password</label>
                <input type="password" className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2" placeholder="••••••••" />
              </div>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
                Update Password
              </button>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">API Keys</h3>
            <div className="flex items-center justify-between p-3 bg-slate-700 rounded-lg">
              <div className="flex items-center gap-3">
                <Key className="w-5 h-5 text-amber-400" />
                <code className="text-sm text-slate-300">sk_live_••••••••••••4f2e</code>
              </div>
              <button className="text-sm text-red-400 hover:text-red-300">Revoke</button>
            </div>
            <button className="mt-4 px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors">
              Generate New API Key
            </button>
          </div>
        </div>
      )}

      {/* Account Settings */}
      {activeTab === 'account' && (
        <div className="space-y-6">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Profile Information</h3>
            <div className="flex items-start gap-6">
              <div className="w-20 h-20 bg-blue-600 rounded-full flex items-center justify-center text-2xl font-bold text-white">
                JD
              </div>
              <div className="flex-1 space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm text-slate-400 block mb-2">First Name</label>
                    <input type="text" className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2" defaultValue="John" />
                  </div>
                  <div>
                    <label className="text-sm text-slate-400 block mb-2">Last Name</label>
                    <input type="text" className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2" defaultValue="Doe" />
                  </div>
                </div>
                <div>
                  <label className="text-sm text-slate-400 block mb-2">Email</label>
                  <input type="email" className="w-full bg-slate-700 border border-slate-600 text-white rounded-lg px-3 py-2" defaultValue="john.doe@example.com" />
                </div>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
            <h3 className="text-lg font-medium text-white mb-4">Data Management</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-slate-700 rounded-lg">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-blue-400" />
                  <div>
                    <p className="text-white font-medium">Export Data</p>
                    <p className="text-sm text-slate-400">Download all your data</p>
                  </div>
                </div>
                <button className="px-4 py-2 border border-slate-600 text-slate-300 rounded-lg hover:bg-slate-600 transition-colors">
                  Export
                </button>
              </div>
            </div>
          </div>

          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-6">
            <h3 className="text-lg font-medium text-red-400 mb-4">Danger Zone</h3>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Trash2 className="w-5 h-5 text-red-400" />
                <div>
                  <p className="text-white font-medium">Delete Account</p>
                  <p className="text-sm text-slate-400">Permanently delete your account and data</p>
                </div>
              </div>
              <button className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors">
                Delete Account
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
