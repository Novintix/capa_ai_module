import type { Metadata } from "next";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const displaySans = Space_Grotesk({
  variable: "--font-display-sans",
  subsets: ["latin"],
});

const codeMono = JetBrains_Mono({
  variable: "--font-code-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RCA Flow Coordinator",
  description: "Button-driven RCA coordination for Fishbone and Why Analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${displaySans.variable} ${codeMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
