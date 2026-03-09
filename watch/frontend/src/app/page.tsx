import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Hero */}
      <section className="max-w-4xl mx-auto px-8 pt-24 pb-16 text-center">
        <h1 className="text-5xl font-bold text-slate-900 leading-tight">
          Never miss a<br />
          <span className="text-teal-600">funding opportunity</span>
        </h1>
        <p className="mt-6 text-lg text-slate-600 max-w-2xl mx-auto">
          Add your funding sources. We monitor them daily and email you when new calls appear.
          Built for researchers, SMEs, and innovation consultants.
        </p>
        <div className="mt-10 flex gap-4 justify-center">
          <Link
            href="/register"
            className="px-8 py-3 bg-teal-600 text-white text-lg rounded-lg hover:bg-teal-700 transition font-medium"
          >
            Get started free
          </Link>
          <Link
            href="/pricing"
            className="px-8 py-3 border border-slate-300 text-slate-700 text-lg rounded-lg hover:border-slate-400 transition"
          >
            See pricing
          </Link>
        </div>
      </section>

      {/* How it works */}
      <section className="max-w-5xl mx-auto px-8 py-16">
        <h2 className="text-2xl font-bold text-center text-slate-900 mb-12">How it works</h2>
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { icon: "🔗", title: "Add your sources", desc: "Paste URLs of funding portals you want to monitor — EU, national, or regional." },
            { icon: "🤖", title: "We check daily", desc: "Our engine scrapes pages and APIs, comparing against known calls to find new ones." },
            { icon: "📬", title: "Get email alerts", desc: "New funding call detected? You get an email with the details immediately." },
          ].map((step) => (
            <div key={step.title} className="text-center p-6 bg-white rounded-xl border border-slate-200">
              <div className="text-4xl mb-4">{step.icon}</div>
              <h3 className="font-semibold text-slate-900 mb-2">{step.title}</h3>
              <p className="text-sm text-slate-600">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 py-8 text-center text-sm text-slate-500">
        © 2026 <a href="https://sustainovate.com" className="text-teal-600 hover:underline">Sustainovate AS</a>. All rights reserved.
      </footer>
    </div>
  );
}
