"use client";
import Link from "next/link";
import { apiFetch, getToken } from "@/lib/api";

const plans = [
  {
    name: "Free",
    price: "€0",
    period: "",
    features: ["3 monitored sources", "Weekly email digest", "Basic keyword filtering"],
    cta: "Get started",
    href: "/register",
    highlight: false,
  },
  {
    name: "Pro",
    price: "€29",
    period: "/month",
    features: ["Unlimited sources", "Daily email alerts", "Advanced keyword filtering", "Priority monitoring"],
    cta: "Upgrade to Pro",
    action: "pro",
    highlight: true,
  },
  {
    name: "Team",
    price: "€99",
    period: "/month",
    features: ["Everything in Pro", "Multiple team members", "Shared source lists", "API access", "Dedicated support"],
    cta: "Upgrade to Team",
    action: "team",
    highlight: false,
  },
];

export default function Pricing() {
  async function handleUpgrade(plan: string) {
    if (!getToken()) {
      window.location.href = "/register";
      return;
    }
    const res = await apiFetch(`/billing/checkout/${plan}`, { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      window.location.href = data.url;
    }
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-16">
      <h1 className="text-3xl font-bold text-center text-slate-900 mb-4">Simple pricing</h1>
      <p className="text-center text-slate-600 mb-12">Start free. Upgrade when you need more sources or faster alerts.</p>

      <div className="grid md:grid-cols-3 gap-6">
        {plans.map((plan) => (
          <div
            key={plan.name}
            className={`p-6 rounded-xl border ${
              plan.highlight ? "border-teal-500 bg-white ring-2 ring-teal-500/20" : "border-slate-200 bg-white"
            }`}
          >
            {plan.highlight && (
              <span className="text-xs font-semibold text-teal-600 bg-teal-50 px-2 py-1 rounded-full">Most popular</span>
            )}
            <h3 className="text-xl font-bold text-slate-900 mt-3">{plan.name}</h3>
            <div className="mt-2 mb-6">
              <span className="text-3xl font-bold text-slate-900">{plan.price}</span>
              <span className="text-slate-500">{plan.period}</span>
            </div>
            <ul className="space-y-2 mb-8">
              {plan.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-slate-600">
                  <span className="text-teal-500 mt-0.5">✓</span> {f}
                </li>
              ))}
            </ul>
            {plan.action ? (
              <button
                onClick={() => handleUpgrade(plan.action!)}
                className={`w-full py-2 rounded-lg text-sm font-medium transition ${
                  plan.highlight ? "bg-teal-600 text-white hover:bg-teal-700" : "border border-slate-300 text-slate-700 hover:border-slate-400"
                }`}
              >
                {plan.cta}
              </button>
            ) : (
              <Link
                href={plan.href || "/register"}
                className="block w-full py-2 rounded-lg text-sm font-medium text-center border border-slate-300 text-slate-700 hover:border-slate-400 transition"
              >
                {plan.cta}
              </Link>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
