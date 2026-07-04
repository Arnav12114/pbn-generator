import { NextRequest, NextResponse } from "next/server";
import { put } from "@vercel/blob";
import { randomUUID } from "crypto";

export const maxDuration = 300; // generation can take 30-90s; give headroom
export const runtime = "nodejs";

const MAX_BYTES = 15 * 1024 * 1024;
const ALLOWED = new Set(["image/jpeg", "image/png", "image/webp"]);

type ApiFile = { data: string; mime: string };

export async function POST(req: NextRequest) {
  try {
    return await handle(req);
  } catch (e) {
    console.error("generate route failed:", e);
    const msg =
      e instanceof Error && /BLOB_READ_WRITE_TOKEN/.test(e.message)
        ? "Storage not configured — connect a Vercel Blob store and redeploy."
        : "Something went wrong on our side. Please try again.";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}

async function handle(req: NextRequest) {
  const apiUrl = process.env.PBN_API_URL;
  if (!apiUrl) return NextResponse.json({ error: "PBN_API_URL not configured" }, { status: 500 });

  const form = await req.formData();
  const image = form.get("image");
  if (!(image instanceof File)) return NextResponse.json({ error: "No image uploaded" }, { status: 400 });
  if (!ALLOWED.has(image.type)) return NextResponse.json({ error: "Use a JPEG, PNG, or WEBP photo" }, { status: 415 });
  if (image.size > MAX_BYTES) return NextResponse.json({ error: "Image too large (max 15MB)" }, { status: 413 });

  // Forward to the Python converter service
  const upstream = new FormData();
  upstream.set("image", image);
  upstream.set("difficulty", (form.get("difficulty") as string) || "signature");

  let res: Response;
  try {
    res = await fetch(`${apiUrl}/generate`, {
      method: "POST",
      body: upstream,
      headers: process.env.PBN_API_KEY ? { "X-API-Key": process.env.PBN_API_KEY } : undefined,
    });
  } catch {
    return NextResponse.json({ error: "Generator service unreachable. Try again in a minute." }, { status: 502 });
  }
  if (!res.ok) {
    const detail = await res.json().then((j) => j.detail).catch(() => null);
    return NextResponse.json({ error: detail ?? "Generation failed" }, { status: res.status });
  }

  const { files } = (await res.json()) as { files: Record<string, ApiFile> };
  const id = randomUUID();

  const upload = async (key: string, filename: string) => {
    const f = files[key];
    if (!f) return null;
    const blob = await put(`results/${id}/${filename}`, Buffer.from(f.data, "base64"), {
      access: "public",
      contentType: f.mime,
      addRandomSuffix: false,
    });
    return blob.url;
  };

  const [previewUrl, templateUrl, templateSvgUrl, legendUrl, paintsUrl] = await Promise.all([
    upload("preview", "preview.png"),
    upload("template", "template.pdf"),
    upload("template_svg", "template.svg"),
    upload("legend", "legend.png"),
    upload("paints", "paints.csv"),
  ]);

  // Manifest lets the lead action resolve gated URLs server-side; client only gets the preview.
  await put(
    `results/${id}/manifest.json`,
    JSON.stringify({
      id,
      createdAt: new Date().toISOString(),
      preview: previewUrl,
      template: templateUrl ?? templateSvgUrl,
      legend: legendUrl,
      paints: paintsUrl,
    }),
    { access: "public", contentType: "application/json", addRandomSuffix: false }
  );

  return NextResponse.json({ id, previewUrl });
}
