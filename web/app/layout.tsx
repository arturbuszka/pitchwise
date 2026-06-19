import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pitchwise",
  description: "Auto-highlights z nagrań meczów",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pl" className="h-full">
      <body className="min-h-full bg-gray-950 text-gray-100 antialiased">
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-3 bg-gray-900">
          <a href="/" className="text-lg font-bold text-white tracking-tight">
            ⚽ Pitchwise
          </a>
        </nav>
        <main className="flex-1 flex flex-col">{children}</main>
      </body>
    </html>
  );
}
