import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: ["/api/"] },
      // Explicitly welcome AI crawlers (GEO): GPTBot, ClaudeBot, PerplexityBot, Google-Extended
      { userAgent: ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "Bingbot"], allow: "/" },
    ],
    sitemap: `${site.url}/sitemap.xml`,
  };
}
