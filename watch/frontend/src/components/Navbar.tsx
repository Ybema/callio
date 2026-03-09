"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";
import { clearToken, getToken } from "@/lib/api";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();

  const loggedIn = useSyncExternalStore(
    (onStoreChange) => {
      if (typeof window === "undefined") return () => undefined;
      const handler = () => onStoreChange();
      window.addEventListener("storage", handler);
      window.addEventListener("auth-changed", handler);
      return () => {
        window.removeEventListener("storage", handler);
        window.removeEventListener("auth-changed", handler);
      };
    },
    () => !!getToken(),
    () => false,
  );

  function logout() {
    clearToken();
    router.push("/");
  }

  const navLink = (href: string, label: string) => (
    <Link
      href={href}
      className={`text-sm px-3 py-1.5 rounded-md transition ${
        pathname === href
          ? "bg-teal-50 text-teal-700 font-medium"
          : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <nav className="flex items-center justify-between px-8 py-3 bg-white border-b border-slate-200 sticky top-0 z-50">
      <div className="flex items-center gap-6">
        <Link href={loggedIn ? "/dashboard" : "/"} className="text-xl font-bold text-teal-700">
          🔔 FundWatch
        </Link>
        {loggedIn && (
          <div className="flex items-center gap-1">
            {navLink("/dashboard", "Dashboard")}
            {navLink("/sources", "Sources")}
            {navLink("/alerts", "Alerts")}
            {navLink("/pricing", "Plans")}
            {navLink("/profile", "Profile")}
          </div>
        )}
      </div>
      <div className="flex gap-3 items-center">
        {loggedIn ? (
          <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-700 transition">
            Sign out
          </button>
        ) : (
          <>
            {navLink("/pricing", "Pricing")}
            <Link
              href="/login"
              className="text-sm px-4 py-2 bg-teal-600 text-white rounded-lg hover:bg-teal-700 transition"
            >
              Sign in
            </Link>
          </>
        )}
      </div>
    </nav>
  );
}
