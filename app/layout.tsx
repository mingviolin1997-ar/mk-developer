import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://dev.mk-musician.com"),
  title: "MK Developer — 软件、插件与 Skill",
  description: "MK 的独立开发者主页，收录软件、插件、Skill 与浏览器扩展。",
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
  openGraph: {
    title: "MK Developer — 软件、插件与 Skill",
    description: "为真实需求，做简单好用的工具。",
    url: "https://dev.mk-musician.com",
    siteName: "MK Developer",
    locale: "zh_CN",
    type: "website",
    images: [{ url: "/og.png", width: 1729, height: 910, alt: "MK Developer 网站分享封面" }],
  },
  twitter: { card: "summary_large_image", images: ["/og.png"] },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body></html>;
}
