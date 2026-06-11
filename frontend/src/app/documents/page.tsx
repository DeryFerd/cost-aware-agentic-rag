"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  Search,
  Download,
  Eye,
  CheckCircle2,
  Loader2,
  AlertCircle,
} from "lucide-react";

interface Document {
  id: number;
  ticker: string;
  year: number;
  filing_type: string;
  status: "indexed" | "processing" | "error";
  chunks: number;
  size: string;
}

const companyColors: Record<string, string> = {
  MSFT: "bg-blue-500/20 text-blue-400",
  AMZN: "bg-orange-500/20 text-orange-400",
  TSLA: "bg-red-500/20 text-red-400",
  GOOG: "bg-green-500/20 text-green-400",
  META: "bg-purple-500/20 text-purple-400",
  AAPL: "bg-slate-500/20 text-slate-400",
  NVDA: "bg-emerald-500/20 text-emerald-400",
};

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [search, setSearch] = useState("");
  const [filterCompany, setFilterCompany] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchDocuments() {
      try {
        const res = await fetch("http://127.0.0.1:8001/documents");
        if (res.ok) {
          const data = await res.json();
          setDocuments(data.documents || []);
        } else {
          setError("Failed to fetch documents");
        }
      } catch (e) {
        setError("Cannot connect to API");
      } finally {
        setLoading(false);
      }
    }
    fetchDocuments();
  }, []);

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.ticker.toLowerCase().includes(search.toLowerCase()) ||
      doc.year.toString().includes(search);
    const matchesCompany =
      filterCompany === "all" || doc.ticker === filterCompany;
    return matchesSearch && matchesCompany;
  });

  const totalChunks = filteredDocs.reduce((acc, doc) => acc + doc.chunks, 0);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-emerald-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white">Documents</h1>
            <p className="text-slate-400 mt-1">
              {documents.length} SEC 10-K filings • {totalChunks.toLocaleString()} chunks indexed
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
            {error}
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
            <input
              type="text"
              placeholder="Search by company or year..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            />
          </div>
          <select
            value={filterCompany}
            onChange={(e) => setFilterCompany(e.target.value)}
            className="px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-white focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          >
            <option value="all">All Companies</option>
            <option value="MSFT">Microsoft</option>
            <option value="AMZN">Amazon</option>
            <option value="TSLA">Tesla</option>
            <option value="GOOG">Alphabet</option>
            <option value="META">Meta</option>
            <option value="AAPL">Apple</option>
            <option value="NVDA">NVIDIA</option>
          </select>
        </div>

        {/* Documents Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredDocs.map((doc) => (
            <div
              key={doc.id}
              className="p-5 rounded-xl bg-slate-800/50 border border-slate-700/50 hover:border-slate-600/50 transition-all"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div
                    className={`px-3 py-1.5 rounded-lg ${companyColors[doc.ticker] || "bg-slate-500/20 text-slate-400"}`}
                  >
                    <span className="font-bold">{doc.ticker}</span>
                  </div>
                  <div>
                    <p className="text-white font-medium">{doc.year} {doc.filing_type}</p>
                    <p className="text-sm text-slate-400">{doc.size}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {doc.status === "indexed" && (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  )}
                  {doc.status === "processing" && (
                    <Loader2 className="w-5 h-5 text-amber-400 animate-spin" />
                  )}
                  {doc.status === "error" && (
                    <AlertCircle className="w-5 h-5 text-red-400" />
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4 text-sm text-slate-400 mb-4">
                <div className="flex items-center gap-1">
                  <FileText className="w-4 h-4" />
                  <span>{doc.chunks} chunks</span>
                </div>
              </div>

              <div className="flex gap-2">
                <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 transition-all text-sm">
                  <Eye className="w-4 h-4" />
                  View
                </button>
                <button className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-700/50 text-slate-300 hover:bg-slate-600/50 transition-all text-sm">
                  <Download className="w-4 h-4" />
                  Export
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
