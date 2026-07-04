import Generator from "@/components/Generator";
import { site } from "@/lib/site";

const faqs = [
  {
    q: "Is the paint by numbers generator really free?",
    a: "Yes. Upload a photo and you get the numbered template PDF, a matched color guide, and a paint list — free. We only ask for your email so we can send your files and keep them safe for you.",
  },
  {
    q: "What photos work best for paint by numbers?",
    a: "Clear, well-lit photos with a strong subject — pets, portraits, landscapes, and flowers convert beautifully. Very dark, blurry, or busy photos produce cluttered templates.",
  },
  {
    q: "What do I get in my download?",
    a: "A print-ready vector PDF template with numbered regions and crisp outlines, a color guide matching every number to a paint color, and a CSV paint list with exact hex and RGB values.",
  },
  {
    q: "How do I print my template?",
    a: "Print at 100% (actual size) on regular paper, cardstock, or inkjet-printable canvas. The template is a vector PDF, so it stays sharp at any size.",
  },
  {
    q: "What paints do I need?",
    a: "Acrylic craft paint works best. Your color guide shows every color with its exact shade, so you can buy small bottles or mix your own.",
  },
  {
    q: "Do you keep my photo?",
    a: "Your photo is processed to generate your design and is not shared or used for anything else.",
  },
];

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: faqs.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
};

export default function Home() {
  return (
    <main>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }} />

      {/* Header */}
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <span className="font-display text-xl font-bold tracking-tight">{site.name}</span>
        <a href="#faq" className="text-sm text-black/60 hover:text-terracotta">FAQ</a>
      </header>

      {/* Hero + generator: the tool IS the landing page */}
      <section className="soft-gradient">
        <div className="mx-auto max-w-6xl px-6 pb-20 pt-10 sm:pt-16">
          <div className="mx-auto max-w-2xl text-center">
            <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
              Turn any photo into a <span className="text-terracotta">paint-by-numbers</span> template. Free.
            </h1>
            <p className="mx-auto mt-4 max-w-xl text-base text-black/60 sm:text-lg">
              Upload a photo. Our generator hand-crafts a numbered, print-ready canvas with a matched
              color guide — every region paintable, every number legible.
            </p>
            <div className="mt-5 flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-black/50">
              <span>✓ Free preview in ~1 minute</span>
              <span>✓ Print-ready vector PDF</span>
              <span>✓ Matched color guide</span>
            </div>
          </div>
          <div className="mt-10">
            <Generator />
          </div>
        </div>
      </section>

      {/* How it works */}
      <section aria-labelledby="how" className="mx-auto max-w-6xl px-6 py-20">
        <h2 id="how" className="font-display text-center text-3xl font-semibold">How it works</h2>
        <div className="mt-10 grid gap-8 sm:grid-cols-3">
          {[
            ["Upload your photo", "A pet, a person, a place you love. JPEG, PNG, or WEBP straight from your phone."],
            ["Preview your design", "We simplify your photo into clean, paintable regions — around 30 colors, every region numbered."],
            ["Download & paint", "Get the template PDF, color guide, and paint list instantly and by email. Print and start painting."],
          ].map(([title, body], i) => (
            <div key={title} className="text-center">
              <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-terracotta/10 font-display font-semibold text-terracotta">
                {i + 1}
              </div>
              <h3 className="font-display text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-black/60">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Quality difference — the honest differentiator */}
      <section className="border-y border-black/5 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-3xl font-semibold">Templates you can actually paint</h2>
            <p className="mt-4 text-black/60 leading-relaxed">
              Most free generators produce slivers too thin for a brush and numbers you can&apos;t read.
              Ours guarantees every single region gets a legible number, no region is thinner than a
              brush tip, and the outline PDF is true vector — razor sharp at any print size.
            </p>
          </div>
          <div className="mt-10 grid gap-6 sm:grid-cols-3">
            {[
              ["Every region numbered", "A hard quality check runs on every design: if one region misses its number, the design doesn't ship."],
              ["No unpaintable slivers", "Regions thinner than a fine brush are dissolved into their neighbours before you ever see them."],
              ["True vector PDF", "Outlines and numbers are vectors, not pixels — print A4 or A2, they stay crisp."],
            ].map(([title, body]) => (
              <div key={title} className="card p-6">
                <h3 className="font-display font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-black/60">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" aria-labelledby="faq-h" className="mx-auto max-w-3xl px-6 py-20">
        <h2 id="faq-h" className="font-display text-center text-3xl font-semibold">Frequently asked questions</h2>
        <div className="mt-10 space-y-3">
          {faqs.map((f) => (
            <details key={f.q} className="card group px-6 py-4">
              <summary className="cursor-pointer list-none font-medium marker:content-none flex items-center justify-between gap-4">
                {f.q}
                <span className="text-terracotta transition group-open:rotate-45 text-xl leading-none" aria-hidden>+</span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-black/60">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-black/5">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-6 py-8 text-sm text-black/50 sm:flex-row">
          <span className="font-display font-semibold text-black/70">{site.name}</span>
          <span>{site.madeIn} · © {new Date().getFullYear()}</span>
        </div>
      </footer>
    </main>
  );
}
