import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AuthProvider } from "@/contexts/auth-context";
import { SpeedInsights } from "@vercel/speed-insights/next";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CONXA - Find people by what they've done",
  description: "Trust-weighted, AI-structured search. Find people by real experience.",
  icons: (() => {
    const apiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim().replace(/\/+$/, "");
    const url = (p: string) => `${apiBase}${p}` || p;

    return {
      icon: [
        { url: url("/img/kana_icon_512.png"), sizes: "512x512", type: "image/png" },
        { url: url("/img/kana_icon_1024.png"), sizes: "1024x1024", type: "image/png" },
        { url: url("/img/kana_icon_1280.png"), sizes: "1280x1280", type: "image/png" },
      ],
      apple: [{ url: url("/img/kana_icon_512.png"), sizes: "512x512", type: "image/png" }],
    };
  })(),
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#0a0a0a",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans bg-background text-foreground antialiased`}>
        <Providers>
          <AuthProvider>{children}</AuthProvider>
        </Providers>
        <SpeedInsights />
      </body>
    </html>
  );
}
