import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "LLM Control Plane",
  description: "AI Infrastructure Platform — Deploy, Route, Evaluate, Observe",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
