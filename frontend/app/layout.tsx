import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { AccountProvider } from "@/lib/account-context";
import { WebSocketProvider } from "@/lib/websocket-context";

export const metadata: Metadata = {
  title: "AUREXIS — Trading Intelligence Platform",
  description: "Centralized trading intelligence, risk management, and MT5 execution monitoring.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-aurexis-bg text-aurexis-text font-sans antialiased min-h-screen">
        <AuthProvider>
          <AccountProvider>
            <WebSocketProvider>
              {children}
            </WebSocketProvider>
          </AccountProvider>
        </AuthProvider>
      </body>
    </html>
  );
}


