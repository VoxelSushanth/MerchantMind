"use client";

import { useState } from "react";
import useSWR from "swr";
import { BarChart3, MessageSquare, TrendingUp, DollarSign, CreditCard, RefreshCw } from "lucide-react";
import Link from "next/link";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

const COLORS = ["#528FFB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#EC4899"];

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "chat">("dashboard");
  
  const { data: dashboardData, isLoading, mutate } = useSWR("/api/dashboard", fetcher);
  const { data: insights } = useSWR("/api/dashboard/insights/auto", fetcher);

  const handleSync = async () => {
    await fetch("/api/sync/trigger", { method: "POST" });
    mutate();
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between px-4 mx-auto max-w-7xl">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2 font-bold text-xl">
              <BarChart3 className="h-6 w-6 text-primary" />
              <span>Razorpay Analytics</span>
            </Link>
            <nav className="flex items-center gap-4">
              <button
                onClick={() => setActiveTab("dashboard")}
                className={`text-sm font-medium transition-colors ${
                  activeTab === "dashboard" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setActiveTab("chat")}
                className={`text-sm font-medium transition-colors ${
                  activeTab === "chat" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                AI Chat
              </button>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={handleSync}
              className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground"
            >
              <RefreshCw className="h-4 w-4" />
              Sync Data
            </button>
          </div>
        </div>
      </header>

      <main className="container px-4 mx-auto max-w-7xl py-8">
        {activeTab === "dashboard" ? (
          <DashboardContent dashboardData={dashboardData} />
        ) : (
          <ChatInterface />
        )}
      </main>
    </div>
  );
}

function DashboardContent({ dashboardData }: { dashboardData?: any }) {
  const kpis = dashboardData?.kpis;

  return (
    <div className="space-y-8">
      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <KPICard
          icon={<DollarSign className="h-4 w-4" />}
          title="GMV"
          value={`₹${(kpis?.gmv || 0) / 100}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
          change={kpis?.gmv_change}
        />
        <KPICard
          icon={<TrendingUp className="h-4 w-4" />}
          title="Success Rate"
          value={`${kpis?.success_rate?.toFixed(1) || 0}%`}
          change={kpis?.success_rate_change}
        />
        <KPICard
          icon={<CreditCard className="h-4 w-4" />}
          title="Avg Ticket"
          value={`₹${kpis?.avg_ticket_size?.toFixed(2) || 0}`}
          change={kpis?.avg_ticket_change}
        />
        <KPICard
          icon={<RefreshCw className="h-4 w-4" />}
          title="Refund Rate"
          value={`${kpis?.refund_rate?.toFixed(2) || 0}%`}
          change={kpis?.refund_rate_change}
          inverse
        />
      </div>

      {/* Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        <ChartCard title="Payments Over Time">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={dashboardData?.payments_over_time || []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="amount" fill="#528FFB" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Payment Methods">
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={dashboardData?.payment_method_breakdown || []}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percentage }) => `${name}: ${percentage.toFixed(0)}%`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="count"
              >
                {(dashboardData?.payment_method_breakdown || []).map((_: any, index: number) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Recent Transactions */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="p-6 border-b">
          <h3 className="font-semibold text-lg">Recent Transactions</h3>
        </div>
        <div className="divide-y">
          {(dashboardData?.recent_transactions || []).slice(0, 5).map((tx: any) => (
            <div key={tx.id} className="flex items-center justify-between p-4">
              <div>
                <p className="font-medium">{tx.razorpay_id}</p>
                <p className="text-sm text-muted-foreground capitalize">{tx.method}</p>
              </div>
              <div className="text-right">
                <p className="font-medium">₹{(tx.amount / 100).toFixed(2)}</p>
                <p className={`text-sm capitalize ${
                  tx.status === "captured" ? "text-green-600" : "text-red-600"
                }`}>{tx.status}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function KPICard({ icon, title, value, change, inverse }: any) {
  const isPositive = inverse ? (change || 0) < 0 : (change || 0) > 0;
  
  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="text-muted-foreground">{icon}</div>
        {change !== undefined && (
          <span className={`text-xs font-medium ${isPositive ? "text-green-600" : "text-red-600"}`}>
            {change > 0 ? "+" : ""}{change.toFixed(1)}%
          </span>
        )}
      </div>
      <div className="mt-4">
        <p className="text-sm text-muted-foreground">{title}</p>
        <p className="text-2xl font-bold">{value}</p>
      </div>
    </div>
  );
}

function ChartCard({ title, children }: any) {
  return (
    <div className="rounded-lg border bg-card p-6 shadow-sm">
      <h3 className="font-semibold text-lg mb-4">{title}</h3>
      {children}
    </div>
  );
}

function ChatInterface() {
  const [messages, setMessages] = useState<{role: string; content: string}[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input.trim();
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage }),
      });
      const data = await response.json();
      setMessages(prev => [...prev, { role: "assistant", content: data.answer }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: "assistant", content: "Sorry, I encountered an error." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="rounded-lg border bg-card shadow-sm min-h-[500px] flex flex-col">
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center text-muted-foreground py-12">
              <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>Ask me anything about your payment data!</p>
              <p className="text-sm mt-2">Try: &quot;What was my refund rate last month?&quot;</p>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg p-4 ${
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))
          )}
          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-lg p-4">
                <RefreshCw className="h-4 w-4 animate-spin" />
              </div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="border-t p-4">
          <div className="flex gap-4">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your payments..."
              className="flex-1 rounded-md border border-input bg-background px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
