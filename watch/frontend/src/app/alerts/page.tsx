"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/api";

export default function Alerts() {
  const router = useRouter();
  useEffect(() => { if (!getToken()) router.push("/login"); }, []);

  return (
    <div className="max-w-4xl mx-auto px-8 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-2">Alerts</h1>
      <p className="text-sm text-slate-500 mb-8">Email alerts sent when new funding calls are detected.</p>
      <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
        <div className="text-4xl mb-4">📬</div>
        <h3 className="font-semibold text-slate-900 mb-2">No alerts yet</h3>
        <p className="text-sm text-slate-500">When we detect new calls from your sources, they&apos;ll show up here.</p>
      </div>
    </div>
  );
}
