"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, getToken } from "@/lib/api";

const ORG_TYPES = [
  "Academic/Research",
  "SME",
  "Large Enterprise",
  "Startup",
  "NGO/Non-profit",
  "Public Authority",
  "Consortium",
] as const;

const TRL_LEVELS = [
  { value: "1", label: "1 (basic principles observed)" },
  { value: "2", label: "2 (technology concept formulated)" },
  { value: "3", label: "3 (experimental proof of concept)" },
  { value: "4", label: "4 (technology validated in lab)" },
  { value: "5", label: "5 (technology validated in relevant environment)" },
  { value: "6", label: "6 (technology demonstrated in relevant environment)" },
  { value: "7", label: "7 (system prototype demonstrated in operational environment)" },
  { value: "8", label: "8 (system complete and qualified)" },
  { value: "9", label: "9 (actual system proven in operational environment)" },
] as const;

const PROBLEM_FRAMES = [
  "Innovate new technology",
  "Validate / pilot in real environment",
  "Scale / commercial deployment",
  "Policy / standards influence",
  "Environmental / climate impact",
  "Data / digital transformation",
  "Collaboration / consortium building",
  "Competitiveness enhancement",
] as const;

const FUNDING_TYPES = [
  "Grant",
  "Procurement / Contract",
  "Prize / Challenge",
  "Equity / Blended",
] as const;

const COLLAB_PREFS = [
  "Single entity",
  "Open to consortium",
  "Consortium required",
] as const;

const BUDGET_RANGE_OPTIONS = [
  "No preference",
  "<250k",
  "250k-1M",
  "1M-5M",
  "5M+",
] as const;

const DEADLINE_OPTIONS = [
  "Any EU Horizon deadline",
  "EU Horizon deadline within 3 months",
  "EU Horizon deadline in 3-6 months",
  "EU Horizon deadline in 6-12 months",
] as const;

const FOCUS_DOMAIN_OPTIONS = [
  "Fisheries",
  "Aquaculture",
  "Seaweed",
  "Seafood",
  "Blue biotech",
  "Marine conservation",
  "Maritime",
] as const;

function countryCodeToFlagEmoji(code: string): string {
  const upper = code.toUpperCase();
  if (!/^[A-Z]{2}$/.test(upper)) return upper;
  const base = 127397;
  return String.fromCodePoint(...upper.split("").map((c) => base + c.charCodeAt(0)));
}

const FALLBACK_COUNTRY_CODES = [
  "AD","AE","AF","AG","AI","AL","AM","AO","AQ","AR","AS","AT","AU","AW","AX","AZ",
  "BA","BB","BD","BE","BF","BG","BH","BI","BJ","BL","BM","BN","BO","BQ","BR","BS",
  "BT","BV","BW","BY","BZ","CA","CC","CD","CF","CG","CH","CI","CK","CL","CM","CN",
  "CO","CR","CU","CV","CW","CX","CY","CZ","DE","DJ","DK","DM","DO","DZ","EC","EE",
  "EG","EH","ER","ES","ET","FI","FJ","FK","FM","FO","FR","GA","GB","GD","GE","GF",
  "GG","GH","GI","GL","GM","GN","GP","GQ","GR","GS","GT","GU","GW","GY","HK","HM",
  "HN","HR","HT","HU","ID","IE","IL","IM","IN","IO","IQ","IR","IS","IT","JE","JM",
  "JO","JP","KE","KG","KH","KI","KM","KN","KP","KR","KW","KY","KZ","LA","LB","LC",
  "LI","LK","LR","LS","LT","LU","LV","LY","MA","MC","MD","ME","MF","MG","MH","MK",
  "ML","MM","MN","MO","MP","MQ","MR","MS","MT","MU","MV","MW","MX","MY","MZ","NA",
  "NC","NE","NF","NG","NI","NL","NO","NP","NR","NU","NZ","OM","PA","PE","PF","PG",
  "PH","PK","PL","PM","PN","PR","PS","PT","PW","PY","QA","RE","RO","RS","RU","RW",
  "SA","SB","SC","SD","SE","SG","SH","SI","SJ","SK","SL","SM","SN","SO","SR","SS",
  "ST","SV","SX","SY","SZ","TC","TD","TF","TG","TH","TJ","TK","TL","TM","TN","TO",
  "TR","TT","TV","TW","TZ","UA","UG","UM","US","UY","UZ","VA","VC","VE","VG","VI",
  "VN","VU","WF","WS","YE","YT","ZA","ZM","ZW",
] as const;

const COUNTRY_NAME_FALLBACK: Record<string, string> = {
  AD: "Andorra", AE: "United Arab Emirates", AF: "Afghanistan", AG: "Antigua and Barbuda", AI: "Anguilla",
  AL: "Albania", AM: "Armenia", AO: "Angola", AR: "Argentina", AS: "American Samoa", AT: "Austria",
  AU: "Australia", AW: "Aruba", AX: "Aland Islands", AZ: "Azerbaijan", BA: "Bosnia and Herzegovina",
  BB: "Barbados", BD: "Bangladesh", BE: "Belgium", BF: "Burkina Faso", BG: "Bulgaria", BH: "Bahrain",
  BI: "Burundi", BJ: "Benin", BL: "Saint Barthelemy", BM: "Bermuda", BN: "Brunei", BO: "Bolivia",
  BQ: "Caribbean Netherlands", BR: "Brazil", BS: "Bahamas", BT: "Bhutan", BW: "Botswana", BY: "Belarus",
  BZ: "Belize", CA: "Canada", CC: "Cocos Islands", CD: "DR Congo", CF: "Central African Republic",
  CG: "Republic of the Congo", CH: "Switzerland", CI: "Cote d'Ivoire", CK: "Cook Islands", CL: "Chile",
  CM: "Cameroon", CN: "China", CO: "Colombia", CR: "Costa Rica", CU: "Cuba", CV: "Cape Verde",
  CW: "Curacao", CX: "Christmas Island", CY: "Cyprus", CZ: "Czechia", DE: "Germany", DJ: "Djibouti",
  DK: "Denmark", DM: "Dominica", DO: "Dominican Republic", DZ: "Algeria", EC: "Ecuador", EE: "Estonia",
  EG: "Egypt", EH: "Western Sahara", ER: "Eritrea", ES: "Spain", ET: "Ethiopia", FI: "Finland",
  FJ: "Fiji", FK: "Falkland Islands", FM: "Micronesia", FO: "Faroe Islands", FR: "France", GA: "Gabon",
  GB: "United Kingdom", GD: "Grenada", GE: "Georgia", GF: "French Guiana", GG: "Guernsey", GH: "Ghana",
  GI: "Gibraltar", GL: "Greenland", GM: "Gambia", GN: "Guinea", GP: "Guadeloupe", GQ: "Equatorial Guinea",
  GR: "Greece", GT: "Guatemala", GU: "Guam", GW: "Guinea-Bissau", GY: "Guyana", HK: "Hong Kong",
  HN: "Honduras", HR: "Croatia", HT: "Haiti", HU: "Hungary", ID: "Indonesia", IE: "Ireland",
  IL: "Israel", IM: "Isle of Man", IN: "India", IO: "British Indian Ocean Territory", IQ: "Iraq",
  IR: "Iran", IS: "Iceland", IT: "Italy", JE: "Jersey", JM: "Jamaica", JO: "Jordan", JP: "Japan",
  KE: "Kenya", KG: "Kyrgyzstan", KH: "Cambodia", KI: "Kiribati", KM: "Comoros", KN: "Saint Kitts and Nevis",
  KP: "North Korea", KR: "South Korea", KW: "Kuwait", KY: "Cayman Islands", KZ: "Kazakhstan",
  LA: "Laos", LB: "Lebanon", LC: "Saint Lucia", LI: "Liechtenstein", LK: "Sri Lanka", LR: "Liberia",
  LS: "Lesotho", LT: "Lithuania", LU: "Luxembourg", LV: "Latvia", LY: "Libya", MA: "Morocco",
  MC: "Monaco", MD: "Moldova", ME: "Montenegro", MF: "Saint Martin", MG: "Madagascar", MH: "Marshall Islands",
  MK: "North Macedonia", ML: "Mali", MM: "Myanmar", MN: "Mongolia", MO: "Macao", MP: "Northern Mariana Islands",
  MQ: "Martinique", MR: "Mauritania", MS: "Montserrat", MT: "Malta", MU: "Mauritius", MV: "Maldives",
  MW: "Malawi", MX: "Mexico", MY: "Malaysia", MZ: "Mozambique", NA: "Namibia", NC: "New Caledonia",
  NE: "Niger", NF: "Norfolk Island", NG: "Nigeria", NI: "Nicaragua", NL: "Netherlands", NO: "Norway",
  NP: "Nepal", NR: "Nauru", NU: "Niue", NZ: "New Zealand", OM: "Oman", PA: "Panama", PE: "Peru",
  PF: "French Polynesia", PG: "Papua New Guinea", PH: "Philippines", PK: "Pakistan", PL: "Poland",
  PM: "Saint Pierre and Miquelon", PN: "Pitcairn", PR: "Puerto Rico", PS: "Palestine", PT: "Portugal",
  PW: "Palau", PY: "Paraguay", QA: "Qatar", RE: "Reunion", RO: "Romania", RS: "Serbia", RU: "Russia",
  RW: "Rwanda", SA: "Saudi Arabia", SB: "Solomon Islands", SC: "Seychelles", SD: "Sudan", SE: "Sweden",
  SG: "Singapore", SH: "Saint Helena", SI: "Slovenia", SJ: "Svalbard and Jan Mayen", SK: "Slovakia",
  SL: "Sierra Leone", SM: "San Marino", SN: "Senegal", SO: "Somalia", SR: "Suriname", SS: "South Sudan",
  ST: "Sao Tome and Principe", SV: "El Salvador", SX: "Sint Maarten", SY: "Syria", SZ: "Eswatini",
  TC: "Turks and Caicos Islands", TD: "Chad", TG: "Togo", TH: "Thailand", TJ: "Tajikistan", TK: "Tokelau",
  TL: "Timor-Leste", TM: "Turkmenistan", TN: "Tunisia", TO: "Tonga", TR: "Turkey", TT: "Trinidad and Tobago",
  TV: "Tuvalu", TW: "Taiwan", TZ: "Tanzania", UA: "Ukraine", UG: "Uganda", US: "United States",
  UY: "Uruguay", UZ: "Uzbekistan", VA: "Vatican City", VC: "Saint Vincent and the Grenadines",
  VE: "Venezuela", VG: "British Virgin Islands", VI: "U.S. Virgin Islands", VN: "Vietnam", VU: "Vanuatu",
  WF: "Wallis and Futuna", WS: "Samoa", YE: "Yemen", YT: "Mayotte", ZA: "South Africa", ZM: "Zambia",
  ZW: "Zimbabwe",
};

function buildCountryOptions() {
  try {
    const intlAny = Intl as Intl & { supportedValuesOf?: (key: string) => string[] };
    const displayNames = new Intl.DisplayNames(["en"], { type: "region" });
    const rawCodes = intlAny.supportedValuesOf ? intlAny.supportedValuesOf("region") : [...FALLBACK_COUNTRY_CODES];
    const options = rawCodes
      .filter((code) => /^[A-Z]{2}$/.test(code))
      .map((code) => ({
        code,
        name: displayNames.of(code) || COUNTRY_NAME_FALLBACK[code] || code,
        flag: countryCodeToFlagEmoji(code),
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
    return options;
  } catch {
    return [...FALLBACK_COUNTRY_CODES]
      .map((code) => ({ code, name: COUNTRY_NAME_FALLBACK[code] || code, flag: countryCodeToFlagEmoji(code) }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }
}

const COUNTRY_OPTIONS = buildCountryOptions();

interface ProfileResponse {
  organisation_type?: string | null;
  country?: string | null;
  trl_min?: string | null;
  trl_max?: string | null;
  description?: string | null;
  context_url?: string | null;
  focus_domains?: string[] | null;
  problem_frames?: string[] | null;
  funding_types?: string[] | null;
  collaboration_preference?: string[] | null;
  budget_min?: string | null;
  budget_max?: string | null;
  deadline_horizon?: string | null;
}

export default function ProfilePage() {
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [organisationType, setOrganisationType] = useState("");
  const [country, setCountry] = useState("");
  const [trlMin, setTrlMin] = useState("");
  const [trlMax, setTrlMax] = useState("");

  const [description, setDescription] = useState("");
  const [contextUrl, setContextUrl] = useState("");
  const [focusDomains, setFocusDomains] = useState<string[]>([]);
  const [problemFrames, setProblemFrames] = useState<string[]>([]);

  const [fundingTypes, setFundingTypes] = useState<string[]>([]);
  const [collaborationPreference, setCollaborationPreference] = useState<string[]>([]);
  const [budgetRange, setBudgetRange] = useState("No preference");
  const [deadlineHorizon, setDeadlineHorizon] = useState("Any");

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const trlMinNum = trlMin ? Number(trlMin) : null;
  const trlMaxNum = trlMax ? Number(trlMax) : null;

  function isTrlSelected(levelValue: string) {
    const level = Number(levelValue);
    if (!trlMinNum || !trlMaxNum) return false;
    return level >= trlMinNum && level <= trlMaxNum;
  }

  function handleTrlLevelClick(levelValue: string) {
    const clicked = Number(levelValue);
    if (!trlMinNum && !trlMaxNum) {
      setTrlMin(levelValue);
      setTrlMax(levelValue);
      return;
    }
    if (trlMinNum && trlMaxNum && trlMinNum === trlMaxNum) {
      const low = Math.min(trlMinNum, clicked);
      const high = Math.max(trlMinNum, clicked);
      setTrlMin(String(low));
      setTrlMax(String(high));
      return;
    }
    setTrlMin(levelValue);
    setTrlMax(levelValue);
  }

  function trlDefinition(levelValue: string) {
    const item = TRL_LEVELS.find((trl) => trl.value === levelValue);
    if (!item) return "";
    return item.label.replace(/^\d+\s*\(/, "").replace(/\)$/, "");
  }

  useEffect(() => {
    if (!getToken()) {
      router.push("/login");
      return;
    }
    loadProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadProfile() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/profile/");
      if (!res.ok) {
        setLoading(false);
        return;
      }
      const data: ProfileResponse = await res.json();

      setOrganisationType(data.organisation_type || "");
      setCountry((data.country || "").toUpperCase());
      setTrlMin(data.trl_min || "");
      setTrlMax(data.trl_max || "");
      setDescription(data.description || "");
      setContextUrl(data.context_url || "");
      setFocusDomains(Array.isArray(data.focus_domains) ? data.focus_domains : []);
      setProblemFrames(Array.isArray(data.problem_frames) ? data.problem_frames : []);
      setFundingTypes(Array.isArray(data.funding_types) ? data.funding_types : []);
      setCollaborationPreference(data.collaboration_preference || []);
      setBudgetRange(data.budget_min || data.budget_max || "No preference");
      setDeadlineHorizon(data.deadline_horizon || "Any");
    } catch {
      setError("Failed to load profile.");
    } finally {
      setLoading(false);
    }
  }

  function toggleArrayValue(value: string, current: string[], setter: (v: string[]) => void) {
    if (current.includes(value)) {
      setter(current.filter((v) => v !== value));
    } else {
      setter([...current, value]);
    }
  }

  function toggleFocusDomain(value: string) {
    if (focusDomains.includes(value)) {
      setFocusDomains(focusDomains.filter((v) => v !== value));
      return;
    }
    if (focusDomains.length >= 5) return;
    setFocusDomains([...focusDomains, value]);
  }

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");

    try {
      const payload = {
        organisation_type: organisationType || null,
        country: country ? country.trim().toUpperCase() : null,
        trl_min: trlMin || null,
        trl_max: trlMax || null,
        description: description || null,
        context_url: contextUrl.trim() || null,
        focus_domains: focusDomains,
        problem_frames: problemFrames,
        funding_types: fundingTypes,
        collaboration_preference: collaborationPreference.length > 0 ? collaborationPreference : null,
        budget_min: budgetRange || "No preference",
        budget_max: budgetRange || "No preference",
        deadline_horizon: deadlineHorizon || "Any",
      };

      const res = await apiFetch("/profile/", {
        method: "PUT",
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let message = "Failed to save profile.";
        try {
          const data = await res.json();
          message = data.detail || message;
        } catch {
          // ignore parse errors
        }
        setError(message);
        return;
      }

      setSuccess("Profile saved successfully.");
    } catch {
      setError("Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="min-h-[60vh] flex items-center justify-center text-slate-500">Loading...</div>;
  }

  return (
    <div className="max-w-4xl mx-auto px-8 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">Profile</h1>
        <p className="text-sm text-slate-500 mt-1">
          Tell us about your organisation so we can better match relevant funding opportunities.
        </p>
      </div>

      <form onSubmit={saveProfile} className="space-y-6">
        {/* Section 1 */}
        <section className="p-6 bg-white rounded-xl border border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Who you are</h2>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Organisation type</label>
              <select
                value={organisationType}
                onChange={(e) => setOrganisationType(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-xs focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="">Select organisation type</option>
                {ORG_TYPES.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Country</label>
              <select
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-white text-xs focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="">Select country</option>
                {COUNTRY_OPTIONS.map((opt) => (
                  <option key={opt.code} value={opt.code}>
                    {opt.flag} {opt.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-2">
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-slate-700">TRL range</label>
                <button
                  type="button"
                  onClick={() => { setTrlMin(""); setTrlMax(""); }}
                  className="text-xs text-slate-500 hover:text-slate-700"
                >
                  Clear
                </button>
              </div>
              <p className="text-xs text-slate-500 mb-3">
                Pick your typical TRL range (start-end). Click once for start, click again for end.
              </p>
              <div className="grid grid-cols-3 md:grid-cols-9 gap-2">
                {TRL_LEVELS.map((trl) => (
                  <button
                    key={`trl-${trl.value}`}
                    type="button"
                    onClick={() => handleTrlLevelClick(trl.value)}
                    title={trl.label}
                    className={`px-2 py-2 rounded-lg border text-sm transition ${
                      isTrlSelected(trl.value)
                        ? "bg-teal-600 text-white border-teal-600"
                        : "bg-white text-slate-700 border-slate-300 hover:border-slate-400"
                    }`}
                  >
                    {trl.value}
                  </button>
                ))}
              </div>
              <p className="mt-2 text-xs text-slate-600">
                {trlMin && trlMax
                  ? `Selected: TRL ${trlMin} (${trlDefinition(trlMin)}) to TRL ${trlMax} (${trlDefinition(trlMax)})`
                  : "Selected: Not sure"}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-[11px] text-slate-500">
                <div className="space-y-1">
                  {TRL_LEVELS.slice(0, 5).map((trl) => (
                    <div key={`trl-def-left-${trl.value}`}>
                      <span className="font-medium text-slate-600">{trl.value}</span>
                      {" - "}
                      {trlDefinition(trl.value)}
                    </div>
                  ))}
                </div>
                <div className="space-y-1">
                  {TRL_LEVELS.slice(5).map((trl) => (
                    <div key={`trl-def-right-${trl.value}`}>
                      <span className="font-medium text-slate-600">{trl.value}</span>
                      {" - "}
                      {trlDefinition(trl.value)}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Section 2 */}
        <section className="p-6 bg-white rounded-xl border border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">What you work on</h2>

          <div className="mb-5">
            <label className="block text-sm font-medium text-slate-700 mb-1">Relevant context URL (optional)</label>
            <input
              type="url"
              value={contextUrl}
              onChange={(e) => setContextUrl(e.target.value)}
              placeholder="Paste a page with relevant scope/context (not necessarily homepage)"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 text-sm"
            />
            <p className="mt-2 text-xs text-slate-500">
              Use a page that best describes your focus area (projects, programs, challenge scope, technology, etc).
            </p>
          </div>

          <div className="mb-5">
            <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
            <textarea
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional extra notes in your own words."
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>

          <div className="mb-5">
            <div className="flex items-center justify-between mb-2">
              <p className="block text-sm font-medium text-slate-700">Industries / domains (optional)</p>
              <span className="text-xs text-slate-500">{focusDomains.length}/5 selected</span>
            </div>
            <p className="text-xs text-slate-500 mb-2">
              Keep this focused. Calls outside these domains are down-ranked or excluded.
            </p>
            <div className="grid md:grid-cols-2 gap-2">
              {FOCUS_DOMAIN_OPTIONS.map((domain) => (
                <label key={domain} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={focusDomains.includes(domain)}
                    onChange={() => toggleFocusDomain(domain)}
                    className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span>{domain}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="block text-sm font-medium text-slate-700 mb-2">Problem frames</p>
            <div className="grid md:grid-cols-2 gap-2">
              {PROBLEM_FRAMES.map((frame) => (
                <label key={frame} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={problemFrames.includes(frame)}
                    onChange={() => toggleArrayValue(frame, problemFrames, setProblemFrames)}
                    className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span>{frame}</span>
                </label>
              ))}
            </div>
          </div>
        </section>

        {/* Section 3 */}
        <section className="p-6 bg-white rounded-xl border border-slate-200">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">What you need</h2>

          <div className="mb-5">
            <p className="block text-sm font-medium text-slate-700 mb-2">Funding types</p>
            <div className="grid md:grid-cols-2 gap-2">
              {FUNDING_TYPES.map((type) => (
                <label key={type} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={fundingTypes.includes(type)}
                    onChange={() => toggleArrayValue(type, fundingTypes, setFundingTypes)}
                    className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span>{type}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mb-5">
            <p className="block text-sm font-medium text-slate-700 mb-2">Collaboration preference</p>
            <div className="space-y-2">
              {COLLAB_PREFS.map((pref) => (
                <label key={pref} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    value={pref}
                    checked={collaborationPreference.includes(pref)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setCollaborationPreference([...collaborationPreference, pref]);
                      } else {
                        setCollaborationPreference(collaborationPreference.filter((p) => p !== pref));
                      }
                    }}
                    className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span>{pref}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mb-5">
            <p className="block text-sm font-medium text-slate-700 mb-2">Budget range</p>
            <div className="grid grid-cols-2 gap-2">
              {BUDGET_RANGE_OPTIONS.map((opt) => (
                <label key={`budget-range-${opt}`} className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="radio"
                    name="budget_range"
                    value={opt}
                    checked={budgetRange === opt}
                    onChange={(e) => setBudgetRange(e.target.value)}
                    className="h-4 w-4 border-slate-300 text-teal-600 focus:ring-teal-500"
                  />
                  <span>{opt}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">EU Horizon deadline horizon</label>
            <select
              value={deadlineHorizon}
              onChange={(e) => setDeadlineHorizon(e.target.value)}
              className="w-full md:w-1/2 px-3 py-2 border border-slate-300 rounded-lg bg-white text-xs focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              {DEADLINE_OPTIONS.map((opt) => (
                <option key={`deadline-${opt}`} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </section>

        {error && <p className="text-sm text-red-500">{error}</p>}
        {success && <p className="text-sm text-green-600">{success}</p>}

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving}
            className={`px-4 py-2 text-sm rounded-lg transition ${
              saving ? "bg-slate-100 text-slate-400 cursor-wait" : "bg-teal-600 text-white hover:bg-teal-700"
            }`}
          >
            {saving ? "Saving..." : "Save profile"}
          </button>
        </div>
      </form>
    </div>
  );
}
