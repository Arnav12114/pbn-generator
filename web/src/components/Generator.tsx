"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import clsx from "clsx";
import { captureLead } from "@/app/actions/lead";

type Phase = "idle" | "uploading" | "preview" | "unlocked";

const leadFormSchema = z.object({
  email: z.string().email("Enter a valid email"),
  name: z.string().max(80).optional(),
});
type LeadForm = z.infer<typeof leadFormSchema>;

const PROGRESS_STEPS = [
  "Reading your photo…",
  "Simplifying colors and shapes…",
  "Tracing paintable regions…",
  "Numbering every region…",
  "Building your printable template…",
];

// Downscale in the browser: the converter works at 1000px anyway, and Vercel
// rejects request bodies over ~4.5MB — this keeps uploads small and fast.
async function downscaleImage(file: File, maxEdge = 2000): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));
  if (scale === 1 && file.size < 3.5 * 1024 * 1024) return file;
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("Could not process this image"))),
      "image/jpeg",
      0.92
    )
  );
}

// Vercel/platform errors return empty or non-JSON bodies — never call res.json() blind.
async function safeJson(res: Response): Promise<Record<string, unknown>> {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { error: `Server error (${res.status}). Please try again.` };
  }
}

export default function Generator() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [sourcePreview, setSourcePreview] = useState<string | null>(null);
  const [design, setDesign] = useState<{ id: string; previewUrl: string } | null>(null);
  const [downloads, setDownloads] = useState<{ template?: string; legend?: string; paints?: string }>({});
  const [emailed, setEmailed] = useState(false);
  const [step, setStep] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  // Rotate progress copy while generating
  useEffect(() => {
    if (phase !== "uploading") return;
    setStep(0);
    const t = setInterval(() => setStep((s) => Math.min(s + 1, PROGRESS_STEPS.length - 1)), 9000);
    return () => clearInterval(t);
  }, [phase]);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Please upload a JPEG, PNG, or WEBP photo.");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError("That photo is over 15MB. Try a smaller one.");
      return;
    }
    setSourcePreview(URL.createObjectURL(file));
    setPhase("uploading");

    try {
      const small = await downscaleImage(file);
      const form = new FormData();
      form.set("image", small, "photo.jpg");
      form.set("difficulty", "signature");
      const res = await fetch("/api/generate", { method: "POST", body: form });
      const json = await safeJson(res);
      if (!res.ok || typeof json.previewUrl !== "string") {
        throw new Error(typeof json.error === "string" ? json.error : "Something went wrong");
      }
      setDesign(json as { id: string; previewUrl: string });
      setPhase("preview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
      setPhase("idle");
    }
  }, []);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LeadForm>({ resolver: zodResolver(leadFormSchema) });

  const onLeadSubmit = handleSubmit(async (values) => {
    if (!design) return;
    const result = await captureLead({ ...values, designId: design.id });
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setDownloads(result.downloads);
    setEmailed(result.emailed);
    setPhase("unlocked");
  });

  const reset = () => {
    setPhase("idle");
    setDesign(null);
    setSourcePreview(null);
    setDownloads({});
    setError(null);
  };

  return (
    <div id="generator" className="w-full max-w-3xl mx-auto">
      {/* ---------- Upload ---------- */}
      {phase === "idle" && (
        <div
          role="button"
          tabIndex={0}
          aria-label="Upload a photo to generate your paint by numbers template"
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0];
            if (f) handleFile(f);
          }}
          className={clsx(
            "card cursor-pointer p-10 sm:p-16 text-center transition-all duration-200 border-2 border-dashed",
            dragOver ? "border-terracotta bg-orange-50 scale-[1.01]" : "border-black/10 hover:border-terracotta/50"
          )}
        >
          <div className="mx-auto mb-5 h-14 w-14 rounded-full bg-terracotta/10 flex items-center justify-center">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#c4643c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <p className="font-display text-xl sm:text-2xl font-semibold">Drop your photo here</p>
          <p className="mt-2 text-sm text-black/50">or tap to choose one — pets, portraits, and landscapes work beautifully</p>
          <p className="mt-4 text-xs text-black/40">JPEG, PNG, or WEBP · up to 15MB · your photo is never shared</p>
          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
        </div>
      )}

      {/* ---------- Generating ---------- */}
      {phase === "uploading" && (
        <div className="card p-8 sm:p-12 text-center">
          {sourcePreview && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={sourcePreview} alt="Your uploaded photo" className="mx-auto mb-6 max-h-64 rounded-2xl object-contain opacity-80" />
          )}
          <div className="shimmer h-2 w-full max-w-sm mx-auto rounded-full" />
          <p className="mt-5 font-medium" aria-live="polite">{PROGRESS_STEPS[step]}</p>
          <p className="mt-1 text-sm text-black/50">This takes about a minute — hand-crafting every region.</p>
        </div>
      )}

      {/* ---------- Preview + gate ---------- */}
      {(phase === "preview" || phase === "unlocked") && design && (
        <div className="card p-6 sm:p-10">
          <div className="grid gap-8 md:grid-cols-2 items-start">
            <div>
              <p className="text-xs uppercase tracking-widest text-black/40 mb-3">Your design</p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={design.previewUrl} alt="Paint-by-numbers preview generated from your photo" className="w-full rounded-2xl shadow-sm" />
              <button onClick={reset} className="mt-4 text-sm text-black/50 underline underline-offset-4 hover:text-terracotta">
                Try a different photo
              </button>
            </div>

            <div>
              {phase === "preview" && (
                <>
                  <h3 className="font-display text-2xl font-semibold">Love it? It&apos;s yours, free.</h3>
                  <p className="mt-2 text-sm text-black/60 leading-relaxed">
                    Enter your email and we&apos;ll unlock your print-ready template PDF and color guide
                    right here — and send a copy to your inbox so you never lose it.
                  </p>
                  <form onSubmit={onLeadSubmit} className="mt-6 space-y-4">
                    <div>
                      <label htmlFor="email" className="block text-sm font-medium mb-1.5">Email</label>
                      <input
                        id="email"
                        type="email"
                        placeholder="you@example.com"
                        autoComplete="email"
                        {...register("email")}
                        className="w-full rounded-xl border border-black/10 bg-white px-4 py-3 text-sm outline-none focus:border-terracotta focus:ring-2 focus:ring-terracotta/20"
                      />
                      {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
                    </div>
                    <div>
                      <label htmlFor="name" className="block text-sm font-medium mb-1.5">
                        Name <span className="text-black/40 font-normal">(optional)</span>
                      </label>
                      <input
                        id="name"
                        type="text"
                        placeholder="So we can say hi"
                        autoComplete="given-name"
                        {...register("name")}
                        className="w-full rounded-xl border border-black/10 bg-white px-4 py-3 text-sm outline-none focus:border-terracotta focus:ring-2 focus:ring-terracotta/20"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="w-full rounded-full bg-terracotta px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-terracotta-deep disabled:opacity-60"
                    >
                      {isSubmitting ? "Unlocking…" : "Unlock my free download"}
                    </button>
                    <p className="text-[11px] text-black/40 leading-relaxed">
                      No spam — just your files and the occasional painting tip. Unsubscribe anytime.
                    </p>
                  </form>
                </>
              )}

              {phase === "unlocked" && (
                <>
                  <h3 className="font-display text-2xl font-semibold">Ready to paint 🎨</h3>
                  <p className="mt-2 text-sm text-black/60">
                    {emailed ? "We also emailed everything to you." : "Download your files below."}
                  </p>
                  <div className="mt-6 space-y-3">
                    {downloads.template && (
                      <a href={downloads.template} download className="block rounded-full bg-terracotta px-6 py-3.5 text-center text-sm font-semibold text-white hover:bg-terracotta-deep">
                        Download template (PDF)
                      </a>
                    )}
                    {downloads.legend && (
                      <a href={downloads.legend} download className="block rounded-full border border-terracotta px-6 py-3.5 text-center text-sm font-semibold text-terracotta hover:bg-terracotta/5">
                        Download color guide (PNG)
                      </a>
                    )}
                    {downloads.paints && (
                      <a href={downloads.paints} download className="block text-center text-sm text-black/50 underline underline-offset-4 hover:text-terracotta">
                        Paint list (CSV)
                      </a>
                    )}
                  </div>
                  <p className="mt-6 text-xs text-black/40 leading-relaxed">
                    Print at 100% / actual size. Cardstock or printable canvas gives the best result.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {error && (
        <p role="alert" className="mt-4 text-center text-sm text-red-600">{error}</p>
      )}
    </div>
  );
}
