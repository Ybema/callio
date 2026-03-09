"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { setToken } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const form = new URLSearchParams();
    form.append("username", email);
    form.append("password", password);
    try {
      const res = await fetch("/api/auth/login", { method: "POST", body: form });
      if (!res.ok) {
        if (res.status === 401) {
          setError("Invalid email or password");
        } else {
          setError("Login failed due to server error. Please try again.");
        }
        return;
      }
      const data = await res.json();
      setToken(data.access_token);
      router.push("/dashboard");
    } catch {
      setError("Cannot reach the server. Make sure backend is running.");
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] flex items-center justify-center">
      <div className="w-full max-w-md p-8 bg-white rounded-xl border border-slate-200 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900 mb-6">Sign in to FundWatch</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
          </div>
          {error && <p className="text-red-500 text-sm">{error}</p>}
          <button type="submit" className="w-full py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition font-medium">
            Sign in
          </button>
        </form>
        <p className="mt-4 text-sm text-center text-slate-600">
          No account? <Link href="/register" className="text-teal-600 hover:underline">Create one</Link>
        </p>
      </div>
    </div>
  );
}
