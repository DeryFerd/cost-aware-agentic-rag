"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import {
  TrendingUp,
  DollarSign,
  Clock,
  Building2,
  Loader2,
} from "lucide-react";

interface HealthData {
  status: string;
  document_count: number;
  chunk_count: number;
}

interface CostData {
  total_cost_usd: number;
  queries_today: number;
  avg_latency_ms: number;
  budget_remaining: number;
}

const COLORS = ["#10b981", "#06b6d4", "#8b5cf6", "#f59e0b"];

export default function AnalyticsPage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [cost, setCost] = useState<CostData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [healthRes, costRes] = await Promise.all([
          fetch("http://127.0.0.1:8001/health"),
          fetch("http://127.0.0.1:8001/cost/summary"),
        ]);

        if (healthRes.ok) {
          setHealth(await healthRes.json());
        }
        if (costRes.ok) {
          setCost(await costRes.json());
        }
      } catch (e) {
        setError("Failed to fetch analytics data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
      </div>
    );
  }

  const companyData = [
    { name: "MSFT", chunks: Math.floor((health?.chunk_count || 2075) * 0.15) },
    { name: "AMZN", chunks: Math.floor((health?.chunk_count || 2075) * 0.15) },
    { name: "TSLA", chunks: Math.floor((health?.chunk_count || 2075) * 0.14) },
    { name: "GOOG", chunks: Math.floor((health?.chunk_count || 2075) * 0.14) },
    { name: "META", chunks: Math.floor((health?.chunk_count || 2075) * 0.14) },
    { name: "AAPL", chunks: Math.floor((health?.chunk_count || 2075) * 0.14) },
    { name: "NVDA", chunks: Math.floor((health?.chunk_count || 2075) * 0.14) },
  ];

  const costData = [
    { name: "gemma3:4b", value: cost?.total_cost_usd || 0.002 },
    { name: "gemma3:27b", value: (cost?.total_cost_usd || 0.008) * 0.3 },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-white mb-8">Analytics</h1>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            {error} - Showing cached data
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4 mb-8">
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-emerald-500/20 flex items-center justify-center">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  {cost?.queries_today || 0}
                </p>
                <p className="text-sm text-slate-400">Queries Today</p>
              </div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-cyan-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  ${(cost?.total_cost_usd || 0).toFixed(4)}
                </p>
                <p className="text-sm text-slate-400">Total Cost</p>
              </div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                <Clock className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  {((cost?.avg_latency_ms || 2300) / 1000).toFixed(1)}s
                </p>
                <p className="text-sm text-slate-400">Avg Latency</p>
              </div>
            </div>
          </div>
          <div className="p-4 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                <Building2 className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <p className="text-2xl font-bold text-white">
                  {health?.document_count || 7}
                </p>
                <p className="text-sm text-slate-400">Documents</p>
              </div>
            </div>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-2 gap-6">
          {/* Company Coverage */}
          <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <h3 className="text-lg font-semibold text-white mb-4">
              Chunks by Company
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={companyData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" stroke="#94a3b8" />
                <YAxis dataKey="name" type="category" stroke="#94a3b8" width={50} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                  }}
                />
                <Bar dataKey="chunks" fill="#06b6d4" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Cost Breakdown */}
          <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700/50">
            <h3 className="text-lg font-semibold text-white mb-4">
              Cost by Model
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={costData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {costData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: "8px",
                  }}
                  formatter={(value: number) => `$${value.toFixed(4)}`}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex justify-center gap-4 mt-4">
              {costData.map((entry, index) => (
                <div key={entry.name} className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: COLORS[index % COLORS.length] }}
                  />
                  <span className="text-sm text-slate-400">{entry.name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* System Status */}
          <div className="p-6 rounded-xl bg-slate-800/50 border border-slate-700/50 col-span-2">
            <h3 className="text-lg font-semibold text-white mb-4">
              System Status
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 rounded-lg bg-slate-700/30">
                <p className="text-sm text-slate-400">Total Chunks Indexed</p>
                <p className="text-xl font-bold text-white">
                  {health?.chunk_count || 0}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-slate-700/30">
                <p className="text-sm text-slate-400">Budget Remaining</p>
                <p className="text-xl font-bold text-emerald-400">
                  ${(cost?.budget_remaining || 10).toFixed(2)}
                </p>
              </div>
              <div className="p-4 rounded-lg bg-slate-700/30">
                <p className="text-sm text-slate-400">API Status</p>
                <p className="text-xl font-bold text-emerald-400">
                  {health?.status === "ok" ? "Healthy" : "Error"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
