"use client";

import Link from "next/link";
import { ArrowRight, BarChart3, MessageSquare, Zap } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted">
      {/* Header */}
      <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between px-4 mx-auto max-w-7xl">
          <div className="flex items-center gap-2 font-bold text-xl">
            <BarChart3 className="h-6 w-6 text-primary" />
            <span>Razorpay Analytics</span>
          </div>
          <nav className="flex items-center gap-4">
            <Link href="/connect" className="text-sm font-medium hover:text-primary">
              Connect Account
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <main className="container px-4 mx-auto max-w-7xl">
        <section className="py-24 text-center">
          <h1 className="text-4xl font-bold tracking-tight sm:text-6xl mb-6">
            AI-Powered Analytics for{" "}
            <span className="text-primary">Razorpay Merchants</span>
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
            Ask questions about your payment data in natural language and get
            instant, accurate answers backed by real transaction data.
          </p>
          <div className="flex justify-center gap-4">
            <Link
              href="/connect"
              className="inline-flex items-center justify-center rounded-md bg-primary px-8 py-3 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90"
            >
              Connect Razorpay Account
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center justify-center rounded-md border border-input bg-background px-8 py-3 text-sm font-medium shadow-sm transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              View Demo
            </Link>
          </div>
        </section>

        {/* Features */}
        <section className="py-16 grid gap-8 md:grid-cols-3">
          <FeatureCard
            icon={<MessageSquare className="h-10 w-10 text-primary" />}
            title="Natural Language Queries"
            description="Ask questions like 'What was my refund rate last month?' and get instant answers."
          />
          <FeatureCard
            icon={<Zap className="h-10 w-10 text-primary" />}
            title="Real-Time Sync"
            description="Your data syncs automatically every 6 hours from Razorpay API."
          />
          <FeatureCard
            icon={<BarChart3 className="h-10 w-10 text-primary" />}
            title="Smart Insights"
            description="Get AI-generated weekly insights and anomaly detection."
          />
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t py-8 mt-16">
        <div className="container px-4 mx-auto max-w-7xl text-center text-sm text-muted-foreground">
          Built with FastAPI, Next.js, and Claude AI
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-6 text-card-foreground shadow-sm">
      <div className="mb-4">{icon}</div>
      <h3 className="font-semibold text-lg mb-2">{title}</h3>
      <p className="text-muted-foreground">{description}</p>
    </div>
  );
}
