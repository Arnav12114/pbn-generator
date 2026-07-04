"""
PBN Generator API — thin FastAPI wrapper around pbn_converter.convert().
The algorithm itself is untouched; this only handles HTTP, temp files, and encoding.
Deploy target: Railway (Dockerfile in this folder).
"""
import base64
import os
import tempfile

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from pbn_converter import PRESETS, convert, find_font

app = FastAPI(title="PBN Generator API", docs_url=None, redoc_url=None)

# CORS: the Next.js app proxies server-side, so this is belt-and-braces for local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

MAX_BYTES = 15 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
API_KEY = os.environ.get("PBN_API_KEY")  # optional shared secret


def _check_key(x_api_key: str | None):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/health")
def health():
    return {"ok": True, "presets": list(PRESETS.keys())}


@app.post("/generate")
async def generate(
    image: UploadFile = File(...),
    difficulty: str = Form("signature"),
    x_api_key: str | None = Header(default=None),
):
    _check_key(x_api_key)
    if difficulty not in PRESETS:
        raise HTTPException(status_code=400, detail=f"difficulty must be one of {list(PRESETS)}")
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WEBP image")
    data = await image.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 15MB)")

    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[image.content_type]
    with tempfile.TemporaryDirectory() as td:
        in_path = os.path.join(td, "input" + ext)
        with open(in_path, "wb") as f:
            f.write(data)
        out_dir = os.path.join(td, "out")
        os.makedirs(out_dir)
        try:
            base = convert(in_path, out_dir, "design", difficulty, find_font())
        except Exception as e:  # surface a clean error, log the real one
            print(f"convert() failed: {e!r}")
            raise HTTPException(status_code=422, detail="Could not process this image. Try a different photo.")

        def enc(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()

        files = {}
        for suffix, key, mime in [
            ("_preview.png", "preview", "image/png"),
            ("_legend.png", "legend", "image/png"),
            ("_paints.csv", "paints", "text/csv"),
            ("_template.pdf", "template", "application/pdf"),
            ("_template.svg", "template_svg", "image/svg+xml"),  # fallback if cairosvg absent
        ]:
            p = base + suffix
            if os.path.exists(p):
                files[key] = {"data": enc(p), "mime": mime}

        if "template" not in files and "template_svg" not in files:
            raise HTTPException(status_code=500, detail="Template generation failed")
        return {"difficulty": difficulty, "files": files}
