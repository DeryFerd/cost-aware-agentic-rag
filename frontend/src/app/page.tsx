"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send,
  Bot,
  User,
  Loader2,
  TrendingUp,
  Building2,
  DollarSign,
  BarChart3,
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  model?: string;
  tools?: string[];
  citations?: string[];
}

const suggestedQueries = [
  "What was Microsoft revenue in 2024?",
  "Compare NVIDIA and AMD revenue growth",
  "What are Tesla risk factors?",
  "How many employees does Apple have?",
];

export default function Dashboard() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setLoading(true);

    try {
      const response = await fetch("http://localhost:8001/query/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMessage }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = "";

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "", model: "", tools: [], citations: [] },
      ]);

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.type === "token") {
                assistantMessage += data.content;
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    content: assistantMessage,
                  };
                  return updated;
                });
              } else if (data.type === "metadata") {
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    model: data.model,
                    tools: data.tools_used,
                    citations: data.citations,
                  };
                  return updated;
                });
              }
            } catch {}
          }
        }
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, an error occurred. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestion = (query: string) => {
    setInput(query);
  };

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700/50 bg-slate-900/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
              <TrendingUp className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">
                Cost-Aware Agentic RAG
              </h1>
              <p className="text-sm text-slate-400">
                Financial Document Analysis
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700">
              <Building2 className="w-4 h-4 text-emerald-400" />
              <span className="text-sm text-slate-300">7 Companies</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700">
              <BarChart3 className="w-4 h-4 text-cyan-400" />
              <span className="text-sm text-slate-300">2075 Chunks</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700">
              <DollarSign className="w-4 h-4 text-amber-400" />
              <span className="text-sm text-slate-300">Cost Optimized</span>
            </div>
          </div>
        </div>
      </header>

      {/* Chat Area */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-16">
              <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
                <Bot className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">
                Ask about SEC 10-K Filings
              </h2>
              <p className="text-slate-400 mb-8 max-w-md mx-auto">
                Analyze financial data from Microsoft, Amazon, Tesla, Google,
                Meta, Apple, and NVIDIA
              </p>
              <div className="grid grid-cols-2 gap-3 max-w-lg mx-auto">
                {suggestedQueries.map((query, i) => (
                  <button
                    key={i}
                    onClick={() => handleSuggestion(query)}
                    className="p-3 text-left text-sm rounded-xl bg-slate-800/50 border border-slate-700/50 text-slate-300 hover:bg-slate-700/50 hover:border-slate-600/50 transition-all"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, i) => (
            <div
              key={i}
              className={`flex gap-3 ${
                message.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {message.role === "assistant" && (
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-5 h-5 text-white" />
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                  message.role === "user"
                    ? "bg-emerald-600 text-white"
                    : "bg-slate-800 border border-slate-700 text-slate-200"
                }`}
              >
                <div className="prose prose-invert prose-sm max-w-none">
                  <p className="whitespace-pre-wrap">{message.content}</p>
                </div>
                {message.role === "assistant" && message.tools && message.tools.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-700/50">
                    <div className="flex flex-wrap gap-2">
                      {message.tools.map((tool, j) => (
                        <span
                          key={j}
                          className="px-2 py-1 text-xs rounded-md bg-slate-700/50 text-slate-400"
                        >
                          {tool}
                        </span>
                      ))}
                      {message.model && (
                        <span className="px-2 py-1 text-xs rounded-md bg-emerald-500/20 text-emerald-400">
                          {message.model}
                        </span>
                      )}
                    </div>
                  </div>
                )}
              </div>
              {message.role === "user" && (
                <div className="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center flex-shrink-0">
                  <User className="w-5 h-5 text-slate-300" />
                </div>
              )}
            </div>
          ))}

          {loading && messages[messages.length - 1]?.role === "user" && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-500 flex items-center justify-center">
                <Loader2 className="w-5 h-5 text-white animate-spin" />
              </div>
              <div className="bg-slate-800 border border-slate-700 rounded-2xl px-4 py-3">
                <p className="text-slate-400 text-sm">Thinking...</p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t border-slate-700/50 bg-slate-900/80 backdrop-blur-xl p-4">
        <form
          onSubmit={handleSubmit}
          className="max-w-4xl mx-auto flex gap-3"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about SEC 10-K filings..."
            className="flex-1 px-4 py-3 rounded-xl bg-slate-800 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500/50"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-6 py-3 rounded-xl bg-gradient-to-r from-emerald-600 to-cyan-600 text-white font-medium hover:from-emerald-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
