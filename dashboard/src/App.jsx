import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Activity, 
  AlertTriangle, 
  Globe, 
  Settings, 
  Bell, 
  Zap, 
  Lock,
  ChevronRight,
  Database,
  ExternalLink,
  Cpu,
  Key
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import { motion } from 'framer-motion';

const mockData = [
  { name: '00:00', threats: 2 },
  { name: '04:00', threats: 5 },
  { name: '08:00', threats: 3 },
  { name: '12:00', threats: 8 },
  { name: '16:00', threats: 12 },
  { name: '20:00', threats: 7 },
  { name: '24:00', threats: 4 },
];

const StatCard = ({ icon: Icon, label, value, color }) => (
  <motion.div 
    whileHover={{ scale: 1.02 }}
    className="glass-card p-6 rounded-2xl glow-blue"
  >
    <div className="flex items-center justify-between">
      <div>
        <p className="text-slate-400 text-sm font-medium">{label}</p>
        <h3 className="text-3xl font-bold mt-1">{value}</h3>
      </div>
      <div className={`p-3 rounded-xl bg-${color}-500/10`}>
        <Icon className={`text-${color}-500`} size={24} />
      </div>
    </div>
  </motion.div>
);

const App = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [vaultLocked, setVaultLocked] = useState(true);
  const [stats, setStats] = useState({
    assets_protected: 0,
    incidents_blocked: 0,
    vault_status: "LOCKED",
    node_status: "ONLINE"
  });
  const [wallets, setWallets] = useState([]);

  const API_BASE = "http://62.171.139.83:8000";

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/stats`);
        const data = await res.json();
        setStats(data);
      } catch (e) {
        console.error("API Error:", e);
      }
    };

    const fetchWallets = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/wallets`);
        const data = await res.json();
        setWallets(data);
      } catch (e) {
        console.error("API Error:", e);
      }
    };

    fetchStats();
    fetchWallets();
    const interval = setInterval(fetchStats, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, []);

  const triggerPanic = async () => {
    if (window.confirm("⚠️ ARE YOU SURE? This will sweep all funds to your safe wallet!")) {
      try {
        await fetch(`${API_BASE}/api/panic`, { method: "POST" });
        alert("🚨 EMERGENCY SWEEP TRIGGERED!");
      } catch (e) {
        alert("Failed to trigger panic. Check backend connection.");
      }
    }
  };

  const officialChannels = [
    { name: "Chainabuse", url: "https://www.chainabuse.com/", desc: "Report malicious addresses to global database." },
    { name: "Solana Security", url: "https://x.com/SolanaSecurity", desc: "Official reporting handle for Solana." },
    { name: "Phantom Support", url: "https://phantom.app/help", desc: "Wallet-specific support and reports." },
    { name: "FBI IC3", url: "https://www.ic3.gov/", desc: "US Government internet crime portal." },
  ];

  return (
    <div className="min-h-screen flex bg-[#0a0f1d] text-slate-200">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/5 p-6 flex flex-col">
        <div className="flex items-center gap-3 mb-12">
          <div className="bg-blue-600 p-2 rounded-lg">
            <Shield className="text-white" size={24} />
          </div>
          <h1 className="text-xl font-bold tracking-tight">GUARDIAN</h1>
        </div>

        <nav className="flex-1 space-y-2">
          {[
            { id: 'overview', icon: Activity, label: 'Overview' },
            { id: 'threats', icon: AlertTriangle, label: 'Threat Intelligence' },
            { id: 'network', icon: Globe, label: 'Honey Pot Network' },
            { id: 'report', icon: Bell, label: 'Report Center' },
            { id: 'vault', icon: Lock, label: 'Secure Vault' },
            { id: 'settings', icon: Settings, label: 'Settings' },
          ].map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                activeTab === item.id 
                  ? 'bg-blue-600/10 text-blue-400 border border-blue-600/20' 
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
              }`}
            >
              <item.icon size={20} />
              <span className="font-medium">{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="mt-auto space-y-4">
          <div className="p-4 rounded-xl bg-slate-900/50 border border-white/5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-slate-500 font-bold uppercase tracking-wider">Vault Status</span>
              {vaultLocked ? <Lock size={14} className="text-red-500"/> : <Zap size={14} className="text-green-500"/>}
            </div>
            <p className="text-xs text-slate-400 mb-3">
              {vaultLocked ? 'Encrypted & Locked' : 'Session Unlocked (Active)'}
            </p>
            <button 
              onClick={() => setVaultLocked(!vaultLocked)}
              className="w-full py-2 text-xs font-bold bg-white/5 hover:bg-white/10 rounded-lg transition-all"
            >
              {vaultLocked ? 'Unlock Session' : 'Lock Vault'}
            </button>
          </div>
          
          <div className="flex items-center gap-3 p-3 rounded-xl bg-green-500/5 border border-green-500/10">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-sm text-green-500 font-medium">Node: Nexus-v1.2</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 p-10 overflow-y-auto">
        <header className="flex justify-between items-center mb-10">
          <div>
            <h2 className="text-3xl font-bold">
              {activeTab === 'overview' ? 'Nexus Command' : activeTab.charAt(0).toUpperCase() + activeTab.slice(1)}
            </h2>
            <p className="text-slate-400 mt-1">AI-Powered Multi-Chain Guardian</p>
          </div>
          <div className="flex gap-4">
             <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium">
              <Cpu size={16} />
              <span>Simulation: ON</span>
            </div>
            <button 
              onClick={triggerPanic}
              className="bg-red-600 hover:bg-red-500 px-6 py-2 rounded-lg font-bold transition-all flex items-center gap-2 shadow-lg shadow-red-600/20"
            >
              <Zap size={18} />
              <span>GLOBAL PANIC</span>
            </button>
          </div>
        </header>

        {activeTab === 'overview' && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-10">
              <StatCard icon={Shield} label="Assets Protected" value={`$${stats.assets_protected.toLocaleString()}`} color="blue" />
              <StatCard icon={AlertTriangle} label="Incidents Blocked" value={stats.incidents_blocked.toLocaleString()} color="orange" />
              <StatCard icon={Key} label="Pre-signed Txs" value="Ready" color="green" />
              <StatCard icon={Bell} label="Network Intel" value="Synced" color="purple" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 glass-card p-8 rounded-3xl">
                <h3 className="text-xl font-bold mb-8">Attack Landscape (Global)</h3>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={mockData}>
                      <defs>
                        <linearGradient id="colorThreats" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#ffffff10" />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 12}} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#94a3b8', fontSize: 12}} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#161d31', border: 'none', borderRadius: '12px' }}
                        itemStyle={{ color: '#3b82f6' }}
                      />
                      <Area type="monotone" dataKey="threats" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorThreats)" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
              
              <div className="glass-card p-8 rounded-3xl border-l-4 border-l-blue-600">
                <h3 className="text-xl font-bold mb-6 italic">Security Posture</h3>
                <div className="space-y-6">
                  {[
                    { label: 'Non-Custodial Hardening', value: 92, color: 'bg-blue-500' },
                    { label: 'AI Anomaly Precision', value: 88, color: 'bg-emerald-500' },
                    { label: 'Broadcasting Redundancy', value: 100, color: 'bg-green-500' },
                    { label: 'MPC Threshold Readiness', value: 45, color: 'bg-slate-500' },
                  ].map((item) => (
                    <div key={item.label}>
                      <div className="flex justify-between mb-2 text-sm">
                        <span className="text-slate-400">{item.label}</span>
                        <span className="font-bold">{item.value}%</span>
                      </div>
                      <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden">
                        <div className={`h-full ${item.color}`} style={{ width: `${item.value}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}

        {activeTab === 'report' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {officialChannels.map((channel) => (
              <div key={channel.name} className="glass-card p-8 rounded-3xl group">
                <div className="flex justify-between items-start mb-4">
                  <h3 className="text-xl font-bold group-hover:text-blue-400 transition-colors">{channel.name}</h3>
                  <a href={channel.url} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-blue-400 transition-all">
                    <ExternalLink size={20} />
                  </a>
                </div>
                <p className="text-slate-400 mb-6 text-sm leading-relaxed">{channel.desc}</p>
                <button 
                  onClick={() => window.open(channel.url, '_blank')}
                  className="w-full py-3 rounded-xl border border-white/10 hover:bg-blue-600 hover:border-blue-600 hover:text-white transition-all font-bold text-sm"
                >
                  FILE OFFICIAL REPORT
                </button>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
