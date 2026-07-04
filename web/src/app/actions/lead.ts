"use server";

import { head, put } from "@vercel/blob";
import { z } from "zod";
import { Resend } from "resend";
import { DesignDeliveryEmail } from "@/emails/DesignDelivery";
import { site } from "@/lib/site";

const leadSchema = z.object({
  email: z.string().email("Enter a valid email"),
  name: z.string().max(80).optional().or(z.literal("")),
  designId: z.string().uuid(),
});

export type LeadResult =
  | { ok: true; downloads: { template?: string; legend?: string; paints?: string }; emailed: boolean }
  | { ok: false; error: string };

export async function captureLead(input: unknown): Promise<LeadResult> {
  const parsed = leadSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: parsed.error.issues[0]?.message ?? "Invalid input" };
  }
  const { email, name, designId } = parsed.data;

  // Resolve the design manifest (server-side only — client never sees gated URLs pre-submit)
  let manifest: { preview?: string; template?: string; legend?: string; paints?: string };
  try {
    const meta = await head(`results/${designId}/manifest.json`);
    manifest = await fetch(meta.url).then((r) => r.json());
  } catch {
    return { ok: false, error: "This design has expired. Please generate it again." };
  }

  // 1. Store the lead (append-only JSON files in Blob — zero-setup "database" for the MVP)
  const ts = new Date().toISOString();
  await put(
    `leads/${ts}-${email.replace(/[^a-zA-Z0-9@._-]/g, "_")}.json`,
    JSON.stringify({ email, name: name || null, designId, ts, preview: manifest.preview }),
    { access: "public", contentType: "application/json", addRandomSuffix: true }
  ).catch((e) => console.error("lead store failed", e));

  // 2. Email the files (graceful if Resend isn't configured yet — never block the download)
  let emailed = false;
  if (process.env.RESEND_API_KEY) {
    const resend = new Resend(process.env.RESEND_API_KEY);
    const from = process.env.EMAIL_FROM ?? "onboarding@resend.dev";
    try {
      await resend.emails.send({
        from,
        to: email,
        subject: `Your paint-by-numbers design is ready 🎨`,
        react: DesignDeliveryEmail({
          name: name || undefined,
          previewUrl: manifest.preview,
          templateUrl: manifest.template,
          legendUrl: manifest.legend,
          siteUrl: site.url,
        }),
      });
      emailed = true;
    } catch (e) {
      console.error("resend user email failed", e);
    }
    // Owner notification — every lead pings you
    if (process.env.LEAD_NOTIFY_EMAIL) {
      resend.emails
        .send({
          from,
          to: process.env.LEAD_NOTIFY_EMAIL,
          subject: `New lead: ${email}`,
          text: `Name: ${name || "—"}\nEmail: ${email}\nDesign: ${manifest.preview}\nAt: ${ts}`,
        })
        .catch((e) => console.error("owner notify failed", e));
    }
  }

  return {
    ok: true,
    emailed,
    downloads: { template: manifest.template, legend: manifest.legend, paints: manifest.paints },
  };
}
