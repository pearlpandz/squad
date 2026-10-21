import type { Metadata } from "next";
import { WorkspaceGate } from "@/components/WorkspaceGate";
import { AdminSessionProvider } from "@/components/AdminSession";
import "./globals.css";

export const metadata: Metadata = {
  title: "SQUAD.",
  description: "AI coworker command workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div aria-label="Notifications" className="toastViewport" id="toast-viewport" role="region" />
        <AdminSessionProvider>
          <WorkspaceGate>{children}</WorkspaceGate>
        </AdminSessionProvider>
      </body>
    </html>
  );
}
