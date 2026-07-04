import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import { site } from "@/lib/site";
import "./globals.css";

const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  metadataBase: new URL(site.url),
  title: {
    default: `${site.tagline} — Photo to Custom Template | ${site.name}`,
    template: `%s | ${site.name}`,
  },
  description: site.description,
  alternates: { canonical: "/" },
  openGraph: {
    title: `${site.tagline} — Photo to Custom Template`,
    description: site.description,
    url: site.url,
    siteName: site.name,
    locale: site.locale,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: `${site.tagline} — ${site.name}`,
    description: site.description,
  },
  robots: { index: true, follow: true },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebApplication",
      name: site.name,
      url: site.url,
      applicationCategory: "DesignApplication",
      operatingSystem: "Any",
      offers: { "@type": "Offer", price: "0", priceCurrency: "INR" },
      description: site.description,
    },
    {
      "@type": "HowTo",
      name: "How to turn a photo into a paint by numbers template",
      step: [
        { "@type": "HowToStep", name: "Upload a photo", text: "Upload any JPEG, PNG, or WEBP photo — a pet, portrait, or landscape." },
        { "@type": "HowToStep", name: "Preview your design", text: "The generator converts your photo into a numbered paint-by-numbers design with a matched color palette." },
        { "@type": "HowToStep", name: "Download your files", text: "Get a print-ready numbered template PDF and a color guide, free, on screen and by email." },
      ],
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${fraunces.variable} ${inter.variable}`}>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {children}
      </body>
    </html>
  );
}
