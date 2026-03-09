"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch, getToken } from "@/lib/api";

interface SourceSummary {
  id: string;
  label: string;
  status: string;
  calls_found: number;
  relevant_count: number;
  keywords: string[];
  last_checked: string | null;
}

interface Stats {
  plan: string;
  total_sources: number;
  active: number;
  errors: number;
  pending: number;
  total_keywords: number;
  keywords: string[];
  total_calls: number;
  total_relevant: number;
  alerts_sent: number;
  alert_last_error: string | null;
  alert_last_error_at: string | null;
  alert_last_ok_at: string | null;
  last_checked: string | null;
  sources: SourceSummary[];
}

interface SourceCallsResponse {
  source: {
    id: string;
    label: string;
    status: string;
    last_checked: string | null;
  } | null;
  calls: Array<{
    id: string;
    title: string;
    url: string;
    deadline: string | null;
    summary: string | null;
    score?: number;
    reasons?: string[];
    first_seen: string | null;
    feedback_label?: "relevant" | "not_relevant" | null;
    prepare_status?: "not_prepared" | "ready" | "partial";
    prepared_at?: string | null;
    workspace_path?: string | null;
    prepared_documents_downloaded?: number;
    prepared_documents_errors?: number;
  }>;
  scored: boolean;
  warning?: string;
}

interface PrepareResponse {
  status: string;
  already_prepared?: boolean;
  workspace_path: string;
  call_slug: string;
  source_slug: string;
  documents_downloaded: number;
  documents_skipped_existing?: number;
  documents_errors: number;
  prepared_at?: string;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [scanning, setScanning] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [savingFeedbackIds, setSavingFeedbackIds] = useState<Record<string, boolean>>({});
  const [preparingCallIds, setPreparingCallIds] = useState<Record<string, boolean>>({});
  const [prepareResults, setPrepareResults] = useState<
    Record<string, { workspace_path: string; documents_downloaded: number; documents_errors: number }>
  >({});
  const [prepareErrors, setPrepareErrors] = useState<Record<string, string>>({});
  const [selectedSourceId, setSelectedSourceId] = useState<string>("");
  const [sourceCalls, setSourceCalls] = useState<SourceCallsResponse | null>(null);
  const [sourceCallsLoading, setSourceCallsLoading] = useState(false);
  const [sourceCallsError, setSourceCallsError] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    loadStats();
  }, []);

  async function loadStats() {
    try {
      const res = await apiFetch("/dashboard/stats");
      if (res.ok) setStats(await res.json());
    } catch {
      // Keep dashboard mounted; other sections can still render.
    }
    setLoading(false);
  }

  async function runScan() {
    setScanning(true);
    await apiFetch("/sources/scan", { method: "POST" });
    // Poll for updates
    const poll = setInterval(async () => {
      const res = await apiFetch("/dashboard/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data);
        if (data.pending === 0) {
          clearInterval(poll);
          setScanning(false);
        }
      }
    }, 3000);
    // Stop polling after 2 minutes max
    setTimeout(() => { clearInterval(poll); setScanning(false); }, 120000);
  }

  async function resetResults() {
    const confirmed = typeof window !== "undefined"
      ? window.confirm("Reset all collected results for this account? This clears seen calls and feedback.")
      : false;
    if (!confirmed) return;

    setResetting(true);
    try {
      const res = await apiFetch("/dashboard/reset-results", { method: "POST" });
      if (!res.ok) return;
      setSelectedSourceId("");
      setSourceCalls(null);
      setSourceCallsError("");
      await loadStats();
    } finally {
      setResetting(false);
    }
  }

  async function saveFeedback(seenCallId: string, label: "relevant" | "not_relevant") {
    setSavingFeedbackIds((prev) => ({ ...prev, [seenCallId]: true }));
    try {
      const res = await apiFetch("/dashboard/call-feedback", {
        method: "POST",
        body: JSON.stringify({
          seen_call_id: seenCallId,
          label,
        }),
      });
      if (!res.ok) return false;
      setSourceCalls((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          calls: prev.calls.map((call) =>
            call.id === seenCallId ? { ...call, feedback_label: label } : call
          ),
        };
      });
      return true;
    } catch {
      return false;
    } finally {
      setSavingFeedbackIds((prev) => ({ ...prev, [seenCallId]: false }));
    }
  }

  async function prepareCall(seenCallId: string) {
    setPreparingCallIds((prev) => ({ ...prev, [seenCallId]: true }));
    setPrepareErrors((prev) => ({ ...prev, [seenCallId]: "" }));
    try {
      const res = await apiFetch(`/calls/${seenCallId}/prepare`, { method: "POST" });
      if (!res.ok) {
        setPrepareErrors((prev) => ({ ...prev, [seenCallId]: "Could not prepare this call." }));
        return;
      }
      const data: PrepareResponse = await res.json();
      setPrepareResults((prev) => ({
        ...prev,
        [seenCallId]: {
          workspace_path: data.workspace_path,
          documents_downloaded: data.documents_downloaded,
          documents_errors: data.documents_errors,
        },
      }));
      setPrepareErrors((prev) => ({ ...prev, [seenCallId]: "" }));
    } catch {
      setPrepareErrors((prev) => ({ ...prev, [seenCallId]: "Could not prepare this call." }));
    } finally {
      setPreparingCallIds((prev) => ({ ...prev, [seenCallId]: false }));
    }
  }

  async function markInterested(seenCallId: string) {
    const saved = await saveFeedback(seenCallId, "relevant");
    if (!saved) return;
    if (!prepareResults[seenCallId] && !preparingCallIds[seenCallId]) {
      await prepareCall(seenCallId);
    }
  }

  async function loadSourceCalls(sourceId: string) {
    setSelectedSourceId(sourceId);
    setSourceCallsLoading(true);
    setSourceCallsError("");
    setSourceCalls(null);
    try {
      const res = await apiFetch(`/dashboard/source-calls/${sourceId}`);
      if (!res.ok) {
        setSourceCallsError("Could not load calls for this source.");
        return;
      }
      const data: SourceCallsResponse = await res.json();
      const restoredPrepared: Record<
        string,
        { workspace_path: string; documents_downloaded: number; documents_errors: number }
      > = {};
      for (const call of data.calls) {
        if (call.prepare_status === "ready" || call.prepare_status === "partial") {
          restoredPrepared[call.id] = {
            workspace_path: call.workspace_path || "",
            documents_downloaded: call.prepared_documents_downloaded || 0,
            documents_errors: call.prepared_documents_errors || 0,
          };
        }
      }
      if (Object.keys(restoredPrepared).length > 0) {
        setPrepareResults((prev) => ({ ...prev, ...restoredPrepared }));
      }
      setSourceCalls(data);
    } catch {
      setSourceCallsError("Could not load calls for this source.");
    } finally {
      setSourceCallsLoading(false);
    }
  }

  if (loading) return <div className="min-h-[60vh] flex items-center justify-center text-slate-500">Loading...</div>;
  if (!stats) return null;

  const statusColor = (s: string) => {
    if (s === "ok") return "text-green-600 bg-green-50";
    if (s === "error") return "text-red-600 bg-red-50";
    return "text-slate-500 bg-slate-100";
  };

  const statusLabel = (s: string) => {
    if (s === "ok") return "Active";
    if (s === "error") return "Error";
    return "Pending";
  };

  const scoreBadgeClass = (score: number) => {
    if (score >= 60) return "bg-green-100 text-green-700";
    if (score >= 40) return "bg-amber-100 text-amber-700";
    return "bg-slate-100 text-slate-700";
  };

  return (
    <div className="max-w-5xl mx-auto px-8 py-10">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            {stats.plan.charAt(0).toUpperCase() + stats.plan.slice(1)} plan
            {stats.last_checked && <> · Last scan: {new Date(stats.last_checked).toLocaleString()}</>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={resetResults}
            disabled={resetting || scanning}
            className={`px-4 py-2 text-sm rounded-lg transition font-medium ${
              resetting || scanning
                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                : "bg-rose-600 text-white hover:bg-rose-700"
            }`}
          >
            {resetting ? "Resetting..." : "Reset results"}
          </button>
          <button
            onClick={runScan}
            disabled={scanning || resetting}
            className={`px-4 py-2 text-sm rounded-lg transition font-medium ${
              scanning || resetting
                ? "bg-slate-100 text-slate-400 cursor-wait"
                : "bg-teal-600 text-white hover:bg-teal-700"
            }`}
          >
            {scanning ? "⏳ Scanning..." : "▶ Run scan now"}
          </button>
        </div>
      </div>

      {stats.alert_last_error && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <p className="text-sm text-amber-800">
            Alert delivery issue (account-level): {stats.alert_last_error}
          </p>
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <p className="text-sm text-slate-500">Sources</p>
          <p className="text-2xl font-bold text-slate-900">{stats.total_sources}</p>
          <div className="flex gap-2 mt-1">
            {stats.active > 0 && <span className="text-xs text-green-600">{stats.active} active</span>}
            {stats.errors > 0 && <span className="text-xs text-red-600">{stats.errors} errors</span>}
            {stats.pending > 0 && <span className="text-xs text-slate-400">{stats.pending} pending</span>}
          </div>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <p className="text-sm text-slate-500">Keywords</p>
          <p className="text-2xl font-bold text-slate-900">{stats.total_keywords}</p>
          <p className="text-xs text-slate-400 mt-1">across all sources</p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <p className="text-sm text-slate-500">Calls scraped</p>
          <p className="text-2xl font-bold text-slate-900">{stats.total_calls}</p>
          <p className="text-xs text-slate-400 mt-1">use View calls for AI filtering</p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <p className="text-sm text-slate-500">Relevant calls</p>
          <p className="text-2xl font-bold text-slate-900">{stats.total_relevant}</p>
          <p className="text-xs text-slate-400 mt-1">AI-filtered and cached</p>
        </div>
        <div className="p-4 bg-white rounded-xl border border-slate-200">
          <p className="text-sm text-slate-500">Alerts sent</p>
          <p className="text-2xl font-bold text-slate-900">{stats.alerts_sent}</p>
          <p className="text-xs text-slate-400 mt-1">email notifications</p>
        </div>
      </div>

      {scanning && (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-xl">
          <p className="text-sm text-blue-800">
            Scan in progress
            {typeof stats.pending === "number"
              ? ` - ${stats.pending} source${stats.pending === 1 ? "" : "s"} remaining`
              : ""}
            . Results refresh automatically when finished.
          </p>
        </div>
      )}

      {/* Keywords */}
      {stats.keywords.length > 0 && (
        <div className="mb-8 p-5 bg-white rounded-xl border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Your keywords</h3>
          <div className="flex flex-wrap gap-2">
            {stats.keywords.map((kw) => (
              <span key={kw} className="text-sm bg-teal-50 text-teal-700 px-3 py-1 rounded-full border border-teal-200">
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Source overview */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Sources</h2>
        <Link href="/sources" className="text-sm text-teal-600 hover:underline">
          Manage sources →
        </Link>
      </div>

      <div className="space-y-2">
        {stats.sources.map((source) => (
          <div key={source.id}>
            <div className="flex items-center justify-between p-4 bg-white rounded-xl border border-slate-200">
              <div className="flex items-center gap-3 min-w-0">
                <span className={`text-xs px-2 py-0.5 rounded-full shrink-0 ${statusColor(source.status)}`}>
                  {statusLabel(source.status)}
                </span>
                <span className="font-medium text-slate-900 truncate">{source.label}</span>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className="text-sm text-slate-500">{source.calls_found} calls</span>
                <span className="text-sm text-teal-700">{source.relevant_count} relevant</span>
                <span className="text-xs text-slate-400">{source.keywords.length} keywords</span>
                <button
                  type="button"
                  onClick={() => loadSourceCalls(source.id)}
                  className={`text-xs px-2 py-1 rounded-md border transition ${
                    selectedSourceId === source.id
                      ? "bg-teal-100 text-teal-700 border-teal-300"
                      : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"
                  }`}
                >
                  View calls
                </button>
              </div>
            </div>

            {selectedSourceId === source.id && (
              <div className="mt-2 p-4 bg-white rounded-xl border border-slate-200">
                {sourceCallsLoading ? (
                  <p className="text-sm text-slate-500">Loading relevant calls...</p>
                ) : sourceCallsError ? (
                  <p className="text-sm text-red-600">{sourceCallsError}</p>
                ) : sourceCalls && !sourceCalls.scored && sourceCalls.warning ? (
                  <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
                    {sourceCalls.warning}
                  </p>
                ) : sourceCalls && sourceCalls.calls.length > 0 ? (
                  <>
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-slate-800">
                        Calls for {sourceCalls.source?.label || source.label}
                      </h3>
                      <span className="text-xs text-slate-500">
                        {sourceCalls.calls.length} relevant call{sourceCalls.calls.length > 1 ? "s" : ""}
                      </span>
                    </div>
                    <div className="space-y-3">
                      {sourceCalls.calls.map((call) => (
                        <div key={`source-call-${call.id}`} className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <a
                                href={call.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-teal-700 hover:underline font-semibold"
                              >
                                {call.title}
                              </a>
                              {call.deadline && (
                                <p className="text-xs text-slate-600 mt-1">
                                  Deadline: {new Date(call.deadline).toLocaleDateString()}
                                </p>
                              )}
                              {call.reasons?.length ? (
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                  {call.reasons.map((reason, idx) => (
                                    <span
                                      key={`${call.id}-reason-${idx}`}
                                      className="text-xs bg-white px-2 py-0.5 rounded-full border border-slate-200"
                                    >
                                      {reason}
                                    </span>
                                  ))}
                                </div>
                              ) : null}
                              <div className="mt-2">
                                {preparingCallIds[call.id] ? (
                                  <span className="inline-flex text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700 border border-blue-300">
                                    Preparing
                                  </span>
                                ) : prepareResults[call.id] ? (
                                  <span className="inline-flex text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-300">
                                    Ready for pre-phase
                                  </span>
                                ) : prepareErrors[call.id] ? (
                                  <span className="inline-flex text-xs px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 border border-rose-300">
                                    Prepare failed
                                  </span>
                                ) : (
                                  <span className="inline-flex text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-300">
                                    Not prepared
                                  </span>
                                )}
                              </div>
                              <div className="mt-2 flex items-center gap-2">
                                <button
                                  type="button"
                                  disabled={!!preparingCallIds[call.id] || !!prepareResults[call.id]}
                                  onClick={() => prepareCall(call.id)}
                                  className={`text-xs px-2 py-1 rounded-md border transition ${
                                    prepareResults[call.id]
                                      ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                                      : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"
                                  }`}
                                >
                                  {preparingCallIds[call.id]
                                    ? "Preparing..."
                                    : prepareResults[call.id]
                                    ? "Ready"
                                    : prepareErrors[call.id]
                                    ? "Retry prepare"
                                    : "Prepare now"}
                                </button>
                                <button
                                  type="button"
                                  disabled={!!savingFeedbackIds[call.id] || !!preparingCallIds[call.id]}
                                  onClick={() => markInterested(call.id)}
                                  className={`text-xs px-2 py-1 rounded-md border transition ${
                                    call.feedback_label === "relevant"
                                      ? "bg-green-100 text-green-700 border-green-300"
                                      : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"
                                  }`}
                                >
                                  {savingFeedbackIds[call.id]
                                    ? "Saving..."
                                    : preparingCallIds[call.id]
                                    ? "Preparing..."
                                    : "Interested"}
                                </button>
                                <button
                                  type="button"
                                  disabled={!!savingFeedbackIds[call.id]}
                                  onClick={() => saveFeedback(call.id, "not_relevant")}
                                  className={`text-xs px-2 py-1 rounded-md border transition ${
                                    call.feedback_label === "not_relevant"
                                      ? "bg-rose-100 text-rose-700 border-rose-300"
                                      : "bg-white text-slate-600 border-slate-300 hover:border-slate-400"
                                  }`}
                                >
                                  {savingFeedbackIds[call.id] ? "Saving..." : "Not interested"}
                                </button>
                              </div>
                              {prepareResults[call.id] && (
                                <p className="text-xs text-emerald-700 mt-2 break-all">
                                  Ready: {prepareResults[call.id].workspace_path} (
                                  {prepareResults[call.id].documents_downloaded} docs
                                  {prepareResults[call.id].documents_errors > 0
                                    ? `, ${prepareResults[call.id].documents_errors} errors`
                                    : ""}
                                  )
                                </p>
                              )}
                              {prepareErrors[call.id] && (
                                <p className="text-xs text-rose-700 mt-2">{prepareErrors[call.id]}</p>
                              )}
                            </div>
                            {typeof call.score === "number" && (
                              <span className={`rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${scoreBadgeClass(call.score)}`}>
                                {call.score}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-slate-500">
                    {sourceCalls?.scored ? "No relevant calls found for this source." : "No calls found for this source yet."}
                  </p>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* First-time prompt */}
      {stats.pending > 0 && !scanning && (
        <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl text-center">
          <p className="text-sm text-amber-700">
            You have {stats.pending} source{stats.pending > 1 ? "s" : ""} that haven&apos;t been scanned yet.
          </p>
          <button
            onClick={runScan}
            className="mt-2 px-4 py-2 bg-amber-500 text-white text-sm rounded-lg hover:bg-amber-600 transition"
          >
            Run your first scan
          </button>
        </div>
      )}
    </div>
  );
}
