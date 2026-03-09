import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";

export const metadata: Metadata = {
  title: "FundWatch — Never miss a funding call",
  description: "Monitor funding opportunities across EU, national, and regional sources. Get email alerts when new calls match your interests.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-50 min-h-screen">
        <Navbar />
        {children}
      </body>
    </html>
  );
}
