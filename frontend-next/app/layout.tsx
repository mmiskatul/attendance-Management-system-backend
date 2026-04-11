import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "University Attendance Console",
  description: "Next.js frontend for the university attendance management system.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
