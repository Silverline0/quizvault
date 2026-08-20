import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import SyncIndicator from "@/components/SyncIndicator";
import MainShell from "@/components/MainShell";

export const metadata: Metadata = {
  title: "QuizVault — Medical Self Assessment",
  description: "4,000+ ophthalmology board exam questions with spaced repetition and cloud sync",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "QuizVault",
  },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
  themeColor: "#7c3aed",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Instrument+Serif:ital@0;1&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-screen antialiased">
        <script dangerouslySetInnerHTML={{ __html: `
          try {
            var s = JSON.parse(localStorage.getItem('quizvault_settings') || '{}');
            if (s.fontSize) document.documentElement.setAttribute('data-fontsize', s.fontSize);
            if (s.theme) document.documentElement.setAttribute('data-theme', s.theme);
          } catch(e) {}
        `}} />
        <Navbar />
        <MainShell>{children}</MainShell>
        <SyncIndicator />
      </body>
    </html>
  );
}
