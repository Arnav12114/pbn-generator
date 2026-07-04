# PBN Generator MVP — Strategy
*July 4, 2026 · Companion to the code in this folder*

---

## 1. PBNify teardown (as of today, not the old version)

PBNify quietly relaunched. It is no longer the crude free canvas tool from your original teardown — it is now a **lead-gen + kit e-commerce funnel**, which is exactly the model you proposed. Key observations from the live site:

**Their funnel:** Upload → preview with before/after in ~30s → "Download free or order a kit." The free PDF is **delivered by email** (email capture is core to their model now), and the paid kit ($29.99, 12"x15" canvas, up to 60 paints) is the monetization. So your instinct to gate on email is validated by the market leader — but note they frame it as *delivery*, not a *gate*: "Get a free print-ready PDF emailed to you." That framing matters; copy ours the same way.

**Why their funnel works:** (1) The tool IS the landing page — zero clicks between arrival and value. (2) Preview-before-commitment kills purchase anxiety ("what you see is exactly what you get — no surprises"). (3) The free tier is genuinely useful, which earns the email honestly. (4) Free printable → kit upsell is a natural price ladder ($0 → $29.99). (5) A programmatic SEO layer: `/paint-by-number/<design-slug>` pages, one per ready-made design, each targeting long-tail "free printable paint by number" queries and each linking back to the generator.

**What to copy:** tool-as-landing-page; instant free preview; email framed as delivery; the trust bullet pattern ("Free preview · Print-at-home files · Full kit available"); mobile-first upload ("tap to select from camera roll"); their programmatic printables directory (our roadmap item #1 after launch); clean minimal footer with Help/Privacy/Terms for trust.

**What they do badly / our openings:** (1) No visible social proof — no counts, reviews, or user gallery. (2) No difficulty control — one output for everyone; we have four QA'd presets. (3) No quality guarantees — nothing about paintability, region thickness, or number legibility; **our QA-asserted "every region numbered, no slivers" pipeline is a real, provable differentiator** and I've made it a landing section. (4) US-centric — no India presence, INR pricing, or India shipping; that's your wedge. (5) Their HowTo/FAQ schema is thin — we ship FAQPage + HowTo + WebApplication JSON-LD from day one.

**What to avoid:** their homepage repeats copy blocks (visible duplicated strings — sloppy); the Amazon affiliate link for canvas sheets leaks trust and traffic; no privacy reassurance near the upload zone (we put "your photo is never shared" right on the dropzone).

---

## 2. Funnel critique — what I changed in your flow and why

Your proposed flow: upload → preview → click Download → form (Name, Email, Location) → download unlocks + email.

**Kept:** the gate itself. Every top competitor is free-and-instant (Davincified, PaintMeLike, DigitPaints, PhotoGrid all advertise "no signup"), so a gate costs some completions — but you're validating *lead quality*, not download counts, and PBNify (the #1-ranked player) gates via email delivery too. A lead who won't type an email was never going to buy a ₹1,500 kit.

**Changed:**
- **Location field: cut.** It's the highest-friction, lowest-honesty field, and you don't need it — you get country from IP (Vercel gives `x-vercel-ip-country` free; log it server-side later if you want it). Every extra field measurably drops form completion; three fields on a free download reads like a sales trap.
- **Name: optional.** Personalizes the email when given, costs nothing when skipped.
- **Unlock = BOTH instant + email.** Email-only delivery punishes typos with total failure and doubles abandonment risk. Instant-only wastes the email you just earned. Both: instant gratification proves the product works; the email re-engages days later and starts the kit-upsell conversation. This is also PBNify-parity.
- **Gate placement:** preview is fully visible ungated (it's the hook and it's shareable); only the *print files* (PDF template + color guide + paint CSV) sit behind email. The preview alone can't be painted from, so the gate doesn't block the "wow" but does protect the deliverable.
- **Framing:** the form headline is "Love it? It's yours, free" — delivery framing, not gate framing.

**Fields you asked about — verdicts:** Country/City: no (IP). Company/Industry/LinkedIn/Website: no — this is B2C hobby/gift traffic; B2B fields kill trust. Phone: absolutely not at this stage (in India especially, phone = spam expectation). "How did you hear about us": valuable but move it to the *post-download thank-you email* as a one-tap question — zero friction at the gate, decent response rates after value is delivered.

**Success metrics to watch (validation, not revenue):** upload→preview completion ≥60%, preview→email conversion ≥25%, email open ≥50%, and — the real demand signal — replies/clicks when you follow up offering a physical kit.

---

## 3. Lead form spec (as built)

| Field | Status | Why |
|---|---|---|
| Email | Required | The entire point |
| Name | Optional | Email personalization |
| Everything else | Cut | Friction; derivable from IP/UA later |

Post-submit: instant unlock of PDF + legend + CSV, premium HTML email (React Email via Resend) with preview image + download buttons, owner notification to arnavmvn@gmail.com per lead. Leads stored as JSON in Vercel Blob (`leads/` prefix) — zero-setup; swap for a real DB/CRM when volume justifies it.

---

## 4. SEO plan (specific to this site)

**Landscape:** ranking today for "paint by numbers generator" queries: Davincified, PBNify, PaintMeLike, PersonalizeVerything, DigitPaints, Mimi Panda, PhotoGrid. All compete on "free, no signup." None compete on *output quality* or *India*. Two open positions: **the quality angle** ("templates you can actually paint") and **the India angle** (custom paint by numbers India, paint by numbers online India).

**Implemented in code:**
- Title: `Free Paint by Numbers Generator — Photo to Custom Template | Numbrush` (primary keyword first, benefit second, brand last).
- Meta description with keyword + benefit + CTA; OG + Twitter cards; canonical; `metadataBase`.
- JSON-LD: `WebApplication` (free, INR), `HowTo` (3 steps), `FAQPage` (6 questions) — the FAQ targets long-tails like "what photos work best for paint by numbers."
- Semantic HTML: single H1 with primary keyword, `<section aria-labelledby>`, `<details>` FAQ, descriptive alt text on generated previews.
- `robots.ts` (AI crawlers explicitly allowed, `/api/` disallowed) + `sitemap.ts`.
- Performance: system-optimized Google fonts via `next/font` (no layout shift), no client JS beyond the one generator island, vector-first assets, Tailwind v4. This page should score 95+ on Core Web Vitals out of the box — LCP is a text H1, not an image.

**Do after launch (priority order):**
1. **Programmatic printables directory** — copy PBNify's smartest move. Run your 4 kit images + ~30 curated public-domain photos through the converter, publish `/printables/<slug>` pages (preview + free download + "make your own" CTA). Each page is a long-tail landing page AND proof of output quality. Your converter makes this nearly free to produce.
2. **India intent pages:** `/paint-by-numbers-india` targeting "custom paint by numbers India" (buy intent, low competition) — this later becomes the Hue & Hush bridge.
3. **Blog, only 3 posts to start:** "Best photos for paint by numbers (with examples)", "How to print a paint by numbers template at home in India", "Acrylic paints to buy in India for paint by numbers" — each internally links to the generator.
4. **OG image:** generate one showing a real before/after — this is what gets clicked when shared on WhatsApp (your dominant share channel in India).
5. Submit sitemap in Google Search Console day one; India-target in GSC settings.

---

## 5. GEO plan (AI search: ChatGPT, Claude, Perplexity, Gemini, AI Overviews)

Current best practice (Google's own AI-features guide + 2026 GEO studies) distilled to what applies here:

**Implemented:** AI crawlers (GPTBot, ClaudeBot, PerplexityBot, Google-Extended) explicitly allowed in robots; all copy server-rendered (AI crawlers don't execute JS — our FAQ/HowTo/hero are in the HTML, only the generator widget is client-side); FAQ written in question-answer form with definition-style lead sentences ("Yes. Upload a photo and you get…") — the exact shape AI engines quote; stacked JSON-LD gives machines an unambiguous entity graph (WebApplication named "Numbrush", free, what it outputs).

**Why this matters for you specifically:** the query "how do I turn a photo into paint by numbers" is *exactly* the kind of task query people now ask ChatGPT/Perplexity instead of Google. Engines answer it by listing 2-4 tools. Getting into that list is winner-take-most, and ~28% of ChatGPT's most-cited pages have no Google top-10 presence — meaning a new site can win AI citations before it wins rankings.

**Do after launch:** (1) Publish one piece of *original data* — e.g., "We analyzed 500 photos: what makes a photo convert well to paint by numbers" using your eval harness's ΔE/SSIM metrics. Unique data is the #1 citation magnet; nobody else in this niche has measurement infrastructure. You already do. (2) Get listed on the pages AI engines already cite for this query (the roundups/tool lists that rank today — outreach, or Product Hunt launch which those lists scrape). (3) Keep every claim on the site specific and verifiable ("every region gets a legible number — a QA check runs on every design") — engines prefer quoting concrete claims over marketing fluff. (4) Add an `llms.txt` once traffic justifies it; low cost, emerging standard.

---

## 6. Architecture (and why it deviates from your spec)

Your spec said "Next.js Server Actions" end-to-end. That fails on contact with reality: the converter is Python with a heavy native stack (opencv, scikit-image, cairo). It cannot run in a Node serverless function, and Vercel's Python runtime has a 250MB bundle limit this stack exceeds. So:

```
Browser ──▶ Next.js on Vercel ──▶ FastAPI on Railway (Docker)
              │        │                  └─ pbn_converter.py (UNTOUCHED)
              │        └─▶ Vercel Blob (files + leads)
              └─▶ Resend (delivery + owner alert)
```

- Next route handler `/api/generate` proxies to Railway (keeps the API key server-side), stores outputs in Blob, returns **only the preview URL** to the browser — gated file URLs never reach the client until the lead form passes Zod validation in a Server Action.
- `maxDuration = 300` on the proxy route; generation takes ~30-90s.
- Difficulty is fixed to `signature` in the UI (best quality/effort ratio per your eval data); the API accepts all four presets so adding a selector later is a one-line change.
- Costs: Vercel Hobby free, Railway ~$5/mo, Resend free to 100 emails/day, Blob free tier ~1GB — well within a validation budget.

**Known MVP shortcuts (fine for validation, fix before scale):** no rate limiting on `/api/generate` (add Upstash if a spike appears); leads in Blob JSON not a DB; blob files are public-but-unguessable URLs; no automated cleanup of old results.

---

## 7. Today's launch checklist

See `README.md` in this folder — exact click-by-click steps for GitHub → Railway → Vercel → Resend (~45 min total).
