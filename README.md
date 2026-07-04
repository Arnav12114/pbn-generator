# PBN Generator MVP

Photo → paint-by-numbers template generator with email lead capture.
Two deployables: `api/` (Python converter, Railway) and `web/` (Next.js 15, Vercel).
Strategy, funnel rationale, and SEO/GEO plan: see `STRATEGY.md`.

```
Browser → Vercel (Next.js) → Railway (FastAPI + pbn_converter.py)
             ├→ Vercel Blob (generated files + leads/*.json)
             └→ Resend (user delivery email + lead alert to you)
```

---

## Deploy today (~45 min)

### 0. Push to GitHub (5 min)
```bash
cd pbn-generator-mvp
git init && git add . && git commit -m "PBN generator MVP"
# create an empty repo on github.com, then:
git remote add origin https://github.com/YOUR_USER/pbn-generator.git
git push -u origin main
```

### 1. Railway — converter API (10 min)
1. railway.com → sign in with GitHub → **New Project → Deploy from GitHub repo** → pick your repo.
2. Settings → **Root Directory** = `api` (it auto-detects the Dockerfile).
3. Variables → add `PBN_API_KEY` = any long random string (`openssl rand -hex 24`).
4. Settings → Networking → **Generate Domain**. Note the URL.
5. Verify: open `https://<railway-url>/health` → should return `{"ok":true,...}`.

### 2. Resend — email (10 min)
1. resend.com → sign up → **API Keys → Create** → copy the key.
2. For today, `EMAIL_FROM` can be `Numbrush <onboarding@resend.dev>` (works immediately, only for testing).
3. When you have a domain: Resend → Domains → add it → set the 3 DNS records → then use `hello@yourdomain.com`. Do this before sharing the link widely — deliverability from `resend.dev` is poor.

### 3. Vercel — web app (15 min)
1. vercel.com → sign up with GitHub → **Add New → Project** → import your repo.
2. **Root Directory** = `web`. Framework auto-detects Next.js.
3. Environment Variables (from `web/.env.example`):
   - `PBN_API_URL` = Railway URL (no trailing slash)
   - `PBN_API_KEY` = same value as on Railway
   - `RESEND_API_KEY`, `EMAIL_FROM`, `LEAD_NOTIFY_EMAIL`
   - `NEXT_PUBLIC_SITE_URL` = your Vercel URL (add after first deploy, then redeploy)
4. Deploy.
5. **Storage → Create Database → Blob** → connect to the project (this injects `BLOB_READ_WRITE_TOKEN`) → redeploy.

### 4. Smoke test (5 min)
Upload a photo → wait ~1 min → preview appears → submit email → downloads unlock → check your inbox (delivery email) and arnavmvn@gmail.com (lead alert). Leads accumulate in Blob under `leads/`.

### 5. Same-day distribution
Share the link in 2–3 WhatsApp groups and one hobby community. Watch: uploads started vs previews seen vs emails captured. That funnel ratio is the validation data.

---

## Local dev
```bash
# API
cd api && pip install -r requirements.txt && pip install --no-deps pykuwahara
uvicorn main:app --reload            # http://localhost:8000

# Web
cd web && npm install
cp .env.example .env.local           # PBN_API_URL=http://localhost:8000
npm run dev                          # http://localhost:3000
```
Note: Blob storage requires `BLOB_READ_WRITE_TOKEN` even locally (create the store first, `vercel env pull`).

## Where things live
- Brand name/copy: `web/src/lib/site.ts` ("Numbrush" is a working name — one file to change)
- Lead gate + form: `web/src/components/Generator.tsx`, `web/src/app/actions/lead.ts`
- Email template: `web/src/emails/DesignDelivery.tsx`
- Difficulty preset: fixed to `signature` in `Generator.tsx`; API accepts all four
- The algorithm: `api/pbn_converter.py` — byte-identical copy of the project root version
