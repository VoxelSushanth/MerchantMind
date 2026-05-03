"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Loader2 } from "lucide-react";
import Link from "next/link";

const RAZORPAY_OAUTH_URL = "https://accounts.razorpay.com/authorize";

export default function ConnectPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const handleConnect = async () => {
    setIsLoading(true);
    
    // In production, first get the OAuth URL from backend
    // For now, construct it directly
    const params = new URLSearchParams({
      client_id: process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || "",
      redirect_uri: `${window.location.origin}/connect/callback`,
      response_type: "code",
      scope: "read_write",
    });

    window.location.href = `${RAZORPAY_OAUTH_URL}?${params.toString()}`;
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container flex h-16 items-center px-4 mx-auto max-w-7xl">
          <Link href="/" className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
        </div>
      </header>

      <main className="container flex items-center justify-center px-4 mx-auto max-w-7xl py-24">
        <div className="w-full max-w-md space-y-8 text-center">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Connect Your Razorpay Account
            </h1>
            <p className="mt-4 text-muted-foreground">
              Securely connect your Razorpay account to start analyzing your 
              payment data with AI-powered insights.
            </p>
          </div>

          <div className="rounded-lg border bg-card p-6 text-card-foreground shadow-sm">
            <ul className="space-y-4 text-left">
              <li className="flex items-start gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">1</span>
                <span className="text-sm">Click &quot;Connect&quot; to authorize access</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">2</span>
                <span className="text-sm">We&apos;ll sync your last 90 days of transactions</span>
              </li>
              <li className="flex items-start gap-3">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">3</span>
                <span className="text-sm">Start asking questions about your data</span>
              </li>
            </ul>
          </div>

          <button
            onClick={handleConnect}
            disabled={isLoading}
            className="w-full inline-flex items-center justify-center rounded-md bg-primary px-6 py-3 text-sm font-medium text-primary-foreground shadow transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Connecting...
              </>
            ) : (
              "Connect Razorpay Account"
            )}
          </button>

          <p className="text-xs text-muted-foreground">
            By connecting, you agree to our Terms of Service and Privacy Policy.
            Your data is encrypted and stored securely.
          </p>
        </div>
      </main>
    </div>
  );
}
