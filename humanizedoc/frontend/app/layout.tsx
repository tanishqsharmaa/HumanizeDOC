import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HumanizeDOC — Turnitin-Safe AI Humanizer",
  description:
    "Make your AI-written documents pass Turnitin with HumanizeDOC.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
