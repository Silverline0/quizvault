import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import SyncIndicator from "@/components/SyncIndicator";

export const metadata: Metadata = {
  title: "QuizVault — Medical Self Assessment",
  description: "Interactive quiz platform for medical board exam preparation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <Navbar />
        <main className="max-w-5xl mx-auto px-4 py-8">
          {children}
        </main>
        <SyncIndicator />
      </body>
    </html>
  );
}
