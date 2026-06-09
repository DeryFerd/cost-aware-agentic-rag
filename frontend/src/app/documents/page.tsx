"use client";

import { useState } from "react";
import {
  FileText,
  Search,
  Filter,
  Download,
  Eye,
  Calendar,
  Building2,
  CheckCircle2,
  Clock,
  AlertCircle,
} from "lucide-react";

interface Document {
  id: number;
  ticker: string;
  year: number;
  filingType: string;
  status: "indexed" | "processing" | "error";
  chunks: number;
  size: string;
  uploadedAt: string;
}

const documents: Document[] = [
  { id: 1, ticker: "MSFT", year: 2025, filingType: "10-K", status: "indexed", chunks: 188, size: "292 KB", uploadedAt: "2026-06-09" },
  { id: 2, ticker: "MSFT", year: 2024, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 3, ticker: "MSFT", year: 2023, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 4, ticker: "MSFT", year: 2022, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 5, ticker: "AMZN", year: 2025, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-09" },
  { id: 6, ticker: "AMZN", year: 2024, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 7, ticker: "AMZN", year: 2023, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 8, ticker: "AMZN", year: 2022, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 9, ticker: "TSLA", year: 2025, filingType: "10-K", status: "indexed", chunks: 17, size: "222 KB", uploadedAt: "2026-06-09" },
  { id: 10, ticker: "TSLA", year: 2024, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 11, ticker: "TSLA", year: 2023, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 12, ticker: "TSLA", year: 2022, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 13, ticker: "GOOG", year: 2025, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-09" },
  { id: 14, ticker: "GOOG", year: 2024, filingType: "10-K", status: "indexed", chunks: 17, size: "90 KB", uploadedAt: "2026-06-08" },
  { id: 15, ticker: "META", year: 2025, filingType: "10-K", status: "indexed", chunks: 69, size: "53 KB", uploadedAt: "2026-06-09" },
  { id: 16, ticker: "META", year: 2024, filingType: "10-K", status: "indexed", chunks: 1260, size: "2.4 MB", uploadedAt: "2026-06-08" },
  { id: 17, ticker: "AAPL", year: 2025, filingType: "10-K", status: "indexed", chunks: 76, size: "119 KB", uploadedAt: "2026-06-09" },
  { id: 18, ticker: "AAPL", year: 2024, filingType: "10-K", status: "indexed", chunks: 77, size: "75 KB", uploadedAt: "2026-06-09" },
  { id: 19, ticker: "NVDA", year: 2025, filingType: "10-K", status: "indexed", chunks: 69, size: "109 KB", uploadedAt: "2026-06-09" },
  { id: 20, ticker: "NVDA", year: 2024, filingType: "10-K", status: "indexed", chunks: 25, size: "51 KB", uploadedAt: "2026-06-09" },
];

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
  const [search, setSearch] = useState("");
  const [filterCompany, setFilterCompany] = useState<string>("all");

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.ticker.toLowerCase().includes(search.toLowerCase()) ||
      doc.year.toString().includes(search);
    const matchesCompany =
      filterCompany === "all" || doc.ticker === filterCompany;
    return matchesSearch && matchesCompany;
  });

  const totalChunks = filteredDocs.reduce((acc, doc) => acc + doc.chunks, 0);

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
          <button className="px-4 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-cyan-600 text-white font-medium hover:from-emerald-500 hover:to-cyan-500 transition-all">
            Upload Document
          </button>
        </div>

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
                    className={`px-3 py-1.5 rounded-lg ${companyColors[doc.ticker]}`}
                  >
                    <span className="font-bold">{doc.ticker}</span>
                  </div>
                  <div>
                    <p className="text-white font-medium">{doc.year} {doc.filingType}</p>
                    <p className="text-sm text-slate-400">{doc.size}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {doc.status === "indexed" && (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  )}
                  {doc.status === "processing" && (
                    <Clock className="w-5 h-5 text-amber-400" />
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
                <div className="flex items-center gap-1">
                  <Calendar className="w-4 h-4" />
                  <span>{doc.uploadedAt}</span>
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
