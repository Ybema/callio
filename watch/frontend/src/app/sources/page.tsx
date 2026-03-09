"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getToken } from "@/lib/api";

interface Source {
  id: string;
  url: string;
  label: string | null;
  keywords: string[];
  crawl_config?: {
    filter_config?: Record<string, string | string[]>;
    [key: string]: unknown;
  } | null;
  origin_country_code: string | null;
  last_checked: string | null;
  last_status: string | null;
  last_error: string | null;
}

interface SourceListResponse {
  items: Source[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface FilterOption {
  key: string;
  label: string;
  type: "multi-select" | "single-select";
  options: Array<{ value: string; label: string }>;
}

type FilterConfig = Record<string, string | string[]>;

export default function Sources() {
  const [sources, setSources] = useState<Source[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [url, setUrl] = useState("");
  const [label, setLabel] = useState("");
  const [keywords, setKeywords] = useState("");
  const [filterOptions, setFilterOptions] = useState<FilterOption[]>([]);
  const [filterConfig, setFilterConfig] = useState<FilterConfig>({});
  const [error, setError] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editUrl, setEditUrl] = useState("");
  const [editLabel, setEditLabel] = useState("");
  const [editKeywords, setEditKeywords] = useState("");
  const [editFilterOptions, setEditFilterOptions] = useState<FilterOption[]>([]);
  const [editFilterConfig, setEditFilterConfig] = useState<FilterConfig>({});
  const [editError, setEditError] = useState("");
  const router = useRouter();

  function inferFlagFromUrl(url: string): string | null {
    try {
      const host = new URL(url).hostname.toLowerCase();
      const tld = host.split(".").pop() || "";
      if (/^[a-z]{2}$/.test(tld)) return tld.toUpperCase();
      return null;
    } catch {
      return null;
    }
  }

  function sourceFlag(source: Source): string | null {
    if (source.origin_country_code && /^[A-Za-z]{2}$/.test(source.origin_country_code)) {
      return source.origin_country_code.toUpperCase();
    }
    return inferFlagFromUrl(source.url);
  }

  function countryCodeToFlagEmoji(code: string): string {
    const upper = code.toUpperCase();
    if (!/^[A-Z]{2}$/.test(upper)) return upper;
    const base = 127397;
    return String.fromCodePoint(...upper.split("").map((c) => base + c.charCodeAt(0)));
  }

  async function loadSources(targetPage = 1) {
    const params = new URLSearchParams({ page: String(targetPage), page_size: String(pageSize) });

    const res = await apiFetch(`/sources/?${params.toString()}`);
    if (res.ok) {
      const data: SourceListResponse = await res.json();
      setSources(data.items || []);
      setTotal(data.total || 0);
      setPages(data.pages || 0);
      if (targetPage !== data.page) setPage(data.page || 1);
    } else {
      setSources([]);
      setTotal(0);
      setPages(0);
    }
    setLoading(false);
  }

  async function addSource(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const res = await apiFetch("/sources/", {
      method: "POST",
      body: JSON.stringify({
        url,
        label: label || null,
        keywords: keywords ? keywords.split(",").map((k) => k.trim()).filter(Boolean) : [],
        filter_config: filterConfig,
      }),
    });
    if (!res.ok) {
      const data = await res.json();
      setError(data.detail || "Failed to add source");
      return;
    }
    setUrl(""); setLabel(""); setKeywords(""); setFilterOptions([]); setFilterConfig({}); setShowAdd(false);
    loadSources(page);
  }

  async function deleteSource(id: string) {
    await apiFetch(`/sources/${id}`, { method: "DELETE" });
    loadSources(page);
  }

  function startEdit(source: Source) {
    setEditingId(source.id);
    setEditUrl(source.url);
    setEditLabel(source.label || "");
    setEditKeywords((source.keywords || []).join(", "));
    setEditFilterConfig((source.crawl_config?.filter_config as FilterConfig) || {});
    setEditError("");
    loadEditFilterOptions(source.id);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditError("");
    setEditFilterOptions([]);
    setEditFilterConfig({});
  }

  async function saveEdit(sourceId: string) {
    setEditError("");
    const res = await apiFetch(`/sources/${sourceId}`, {
      method: "PATCH",
      body: JSON.stringify({
        url: editUrl,
        label: editLabel || null,
        keywords: editKeywords ? editKeywords.split(",").map((k) => k.trim()).filter(Boolean) : [],
        filter_config: editFilterConfig,
      }),
    });
    if (!res.ok) {
      const data = await res.json();
      setEditError(data.detail || "Failed to update source");
      return;
    }
    setEditingId(null);
    setEditFilterOptions([]);
    setEditFilterConfig({});
    loadSources(page);
  }

  async function detectFiltersForUrl(targetUrl: string) {
    const trimmed = targetUrl.trim();
    if (!trimmed) {
      setFilterOptions([]);
      setFilterConfig({});
      return;
    }
    const res = await apiFetch("/sources/detect-filters", {
      method: "POST",
      body: JSON.stringify({ url: trimmed }),
    });
    if (!res.ok) {
      setFilterOptions([]);
      setFilterConfig({});
      return;
    }
    const options: FilterOption[] = await res.json();
    setFilterOptions(options || []);
    if (!options?.length) {
      setFilterConfig({});
    }
  }

  async function loadEditFilterOptions(sourceId: string) {
    const res = await apiFetch(`/sources/${sourceId}/filter-options`);
    if (!res.ok) {
      setEditFilterOptions([]);
      return;
    }
    const data = await res.json();
    setEditFilterOptions(data.options || []);
    setEditFilterConfig(data.filter_config || {});
  }

  async function detectEditFiltersForUrl(targetUrl: string) {
    const trimmed = targetUrl.trim();
    if (!trimmed) {
      setEditFilterOptions([]);
      setEditFilterConfig({});
      return;
    }
    const res = await apiFetch("/sources/detect-filters", {
      method: "POST",
      body: JSON.stringify({ url: trimmed }),
    });
    if (!res.ok) {
      setEditFilterOptions([]);
      setEditFilterConfig({});
      return;
    }
    const options: FilterOption[] = await res.json();
    setEditFilterOptions(options || []);
    if (!options?.length) {
      setEditFilterConfig({});
    }
  }

  function updateFilterSelection(
    key: string,
    value: string,
    selected: boolean,
    type: "multi-select" | "single-select",
    target: "create" | "edit",
  ) {
    const setter = target === "create" ? setFilterConfig : setEditFilterConfig;
    setter((prev) => {
      const next = { ...prev };
      if (type === "single-select") {
        if (selected) next[key] = value;
        else delete next[key];
        return next;
      }
      const existing = Array.isArray(prev[key]) ? (prev[key] as string[]) : [];
      const merged = selected
        ? Array.from(new Set([...existing, value]))
        : existing.filter((item) => item !== value);
      if (merged.length) next[key] = merged;
      else delete next[key];
      return next;
    });
  }

  useEffect(() => {
    if (!getToken()) { router.push("/login"); return; }
    loadSources();
  }, []);

  useEffect(() => {
    loadSources(page);
  }, [page]);

  if (loading) return <div className="min-h-[60vh] flex items-center justify-center text-slate-500">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto px-8 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Manage sources</h1>
          <p className="text-sm text-slate-500 mt-1">
            {total} source{total !== 1 ? "s" : ""} monitored
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-4 py-2 bg-teal-600 text-white text-sm rounded-lg hover:bg-teal-700 transition"
        >
          + Add source
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <form onSubmit={addSource} className="mb-8 p-6 bg-white rounded-xl border border-slate-200">
          <h3 className="font-semibold text-slate-900 mb-4">Add a new source</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-1">URL *</label>
              <input
                type="url" required value={url} onChange={(e) => setUrl(e.target.value)}
                onBlur={() => detectFiltersForUrl(url)}
                placeholder="https://business.esa.int/funding"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Label</label>
              <input
                type="text" value={label} onChange={(e) => setLabel(e.target.value)}
                placeholder="ESA Funding"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
            </div>
          </div>
          {filterOptions.length > 0 && (
            <div className="mt-4 p-3 bg-teal-50 border border-teal-100 rounded-lg">
              <p className="text-xs font-medium text-teal-700 mb-2">Source filters available</p>
              <div className="space-y-3">
                {filterOptions.map((opt) => (
                  <div key={opt.key}>
                    <p className="text-sm font-medium text-slate-700 mb-1">{opt.label}</p>
                    <div className="flex flex-wrap gap-3">
                      {opt.options.map((choice) => {
                        const checked = opt.type === "single-select"
                          ? filterConfig[opt.key] === choice.value
                          : Array.isArray(filterConfig[opt.key]) && (filterConfig[opt.key] as string[]).includes(choice.value);
                        return (
                          <label key={choice.value} className="inline-flex items-center gap-2 text-sm text-slate-700">
                            <input
                              type={opt.type === "single-select" ? "radio" : "checkbox"}
                              name={`create-${opt.key}`}
                              checked={!!checked}
                              onChange={(e) => updateFilterSelection(opt.key, choice.value, e.target.checked, opt.type, "create")}
                            />
                            {choice.label}
                          </label>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="mt-4">
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Keywords <span className="text-slate-400 font-normal">— comma-separated, we&apos;ll only alert on matches</span>
            </label>
            <input
              type="text" value={keywords} onChange={(e) => setKeywords(e.target.value)}
              placeholder="fisheries, marine, ocean, sustainability"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          {error && <p className="mt-2 text-red-500 text-sm">{error}</p>}
          <div className="mt-4 flex gap-2">
            <button type="submit" className="px-4 py-2 bg-teal-600 text-white text-sm rounded-lg hover:bg-teal-700 transition">
              Add source
            </button>
            <button type="button" onClick={() => setShowAdd(false)} className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800">
              Cancel
            </button>
          </div>
        </form>
      )}

      {sources.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
          <div className="text-4xl mb-4">📡</div>
          <h3 className="font-semibold text-slate-900 mb-2">No sources yet</h3>
          <p className="text-sm text-slate-500 mb-4">Add a URL to start monitoring for new funding calls.</p>
          <button onClick={() => setShowAdd(true)} className="px-4 py-2 bg-teal-600 text-white text-sm rounded-lg hover:bg-teal-700 transition">
            + Add your first source
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map((source) => (
            <div key={source.id} className="p-5 bg-white rounded-xl border border-slate-200 hover:border-slate-300 transition">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {sourceFlag(source) && (
                      <span
                        className="text-sm bg-indigo-100 px-2 py-0.5 rounded-full shrink-0"
                        title={sourceFlag(source) || ""}
                        aria-label={`Source region ${sourceFlag(source)}`}
                      >
                        {countryCodeToFlagEmoji(sourceFlag(source) || "")}
                      </span>
                    )}
                    <h3 className="font-semibold text-slate-900">{source.label || source.url}</h3>
                    {source.last_status === "ok" && (
                      <span className="text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full shrink-0">Active</span>
                    )}
                    {source.last_status === "error" && (
                      <span className="text-xs text-red-600 bg-red-50 px-2 py-0.5 rounded-full shrink-0" title={source.last_error || ""}>Error</span>
                    )}
                    {(!source.last_status || source.last_status === "pending") && (
                      <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full shrink-0">Pending</span>
                    )}
                  </div>
                  {editingId === source.id ? (
                    <div className="mt-3 space-y-3">
                      <input
                        type="url"
                        value={editUrl}
                        onChange={(e) => setEditUrl(e.target.value)}
                        onBlur={() => detectEditFiltersForUrl(editUrl)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                      />
                      <div className="grid md:grid-cols-1 gap-3">
                        <input
                          type="text"
                          value={editLabel}
                          onChange={(e) => setEditLabel(e.target.value)}
                          placeholder="Label"
                          className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                        />
                      </div>
                      <input
                        type="text"
                        value={editKeywords}
                        onChange={(e) => setEditKeywords(e.target.value)}
                        placeholder="Keywords (comma separated)"
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
                      />
                      {editFilterOptions.length > 0 && (
                        <div className="p-3 bg-teal-50 border border-teal-100 rounded-lg">
                          <p className="text-xs font-medium text-teal-700 mb-2">Source filters available</p>
                          <div className="space-y-3">
                            {editFilterOptions.map((opt) => (
                              <div key={opt.key}>
                                <p className="text-sm font-medium text-slate-700 mb-1">{opt.label}</p>
                                <div className="flex flex-wrap gap-3">
                                  {opt.options.map((choice) => {
                                    const checked = opt.type === "single-select"
                                      ? editFilterConfig[opt.key] === choice.value
                                      : Array.isArray(editFilterConfig[opt.key]) && (editFilterConfig[opt.key] as string[]).includes(choice.value);
                                    return (
                                      <label key={choice.value} className="inline-flex items-center gap-2 text-sm text-slate-700">
                                        <input
                                          type={opt.type === "single-select" ? "radio" : "checkbox"}
                                          name={`edit-${opt.key}`}
                                          checked={!!checked}
                                          onChange={(e) => updateFilterSelection(opt.key, choice.value, e.target.checked, opt.type, "edit")}
                                        />
                                        {choice.label}
                                      </label>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {editError && <p className="text-xs text-red-500">{editError}</p>}
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => saveEdit(source.id)}
                          className="px-3 py-1.5 text-xs bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition"
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          className="px-3 py-1.5 text-xs text-slate-600 hover:text-slate-800"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <a href={source.url} target="_blank" rel="noopener" className="text-sm text-teal-600 hover:underline truncate block">
                        {source.url}
                      </a>
                      {source.last_status === "error" && source.last_error && (
                        <p className="text-xs text-red-500 mt-1">⚠ {source.last_error}</p>
                      )}
                      {(source.keywords || []).length > 0 && (
                        <div className="flex flex-wrap gap-1.5 mt-3">
                          <span className="text-xs text-slate-400 mr-1">Keywords:</span>
                          {(source.keywords || []).map((kw) => (
                            <span key={kw} className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full border border-teal-200">
                              {kw}
                            </span>
                          ))}
                        </div>
                      )}
                      {(source.keywords || []).length === 0 && (
                        <p className="text-xs text-amber-500 mt-3">⚠ No keywords — will match all content</p>
                      )}
                    </>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  {editingId !== source.id && (
                    <button
                      onClick={() => startEdit(source)}
                      className="text-sm text-slate-500 hover:text-slate-700 transition"
                    >
                      Edit
                    </button>
                  )}
                  <button onClick={() => deleteSource(source.id)} className="text-sm text-red-400 hover:text-red-600 transition">
                    Remove
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="mt-6 flex items-center justify-between text-sm">
        <span className="text-slate-500">
          Page {page} of {pages || 1}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className={`px-3 py-1.5 rounded-lg border ${
              page <= 1 ? "text-slate-300 border-slate-200" : "text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            Previous
          </button>
          <button
            onClick={() => setPage((p) => (pages > 0 ? Math.min(pages, p + 1) : p + 1))}
            disabled={pages > 0 && page >= pages}
            className={`px-3 py-1.5 rounded-lg border ${
              pages > 0 && page >= pages ? "text-slate-300 border-slate-200" : "text-slate-700 border-slate-300 hover:bg-slate-50"
            }`}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
