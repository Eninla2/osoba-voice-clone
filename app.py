import os, io, re, base64, asyncio, tempfile, subprocess
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
import edge_tts

app = FastAPI()

SECRET_KEY = os.environ.get("OSOBA_SECRET", "")
VOICE      = os.environ.get("OSOBA_VOICE", "en-GB-RyanNeural")

print(f"[OSOBA] Voice Studio READY — voice: {VOICE}")

VOICES = {
    "en-GB-RyanNeural":        "British Male – Deep, Cinematic",
    "en-GB-ThomasNeural":      "British Male – Clear, Documentary",
    "en-US-GuyNeural":         "American Male – Smooth, Authoritative",
    "en-US-ChristopherNeural": "American Male – Rich, Professional",
    "en-GB-SoniaNeural":       "British Female – Crisp, Elegant",
    "en-US-JennyNeural":       "American Female – Warm, Natural",
    "en-US-AriaNeural":        "American Female – Expressive",
}

def split_chunks(text: str, max_chars: int = 3000) -> list:
    """Split on paragraph/sentence boundaries."""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                # split long paragraph on sentences
                sentences = re.split(r'(?<=[.!?])\s+', para)
                cur2 = ""
                for s in sentences:
                    if len(cur2) + len(s) + 1 <= max_chars:
                        cur2 = (cur2 + " " + s).strip()
                    else:
                        if cur2: chunks.append(cur2)
                        cur2 = s[:max_chars]
                if cur2: chunks.append(cur2)
            else:
                current = para
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]

async def tts_chunk(text: str, voice: str) -> bytes:
    """Generate one audio chunk via edge-tts."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(tmp_path)
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data

async def generate_audio(text: str, voice: str) -> bytes:
    """Generate full audio, chunked for large texts."""
    chunks = split_chunks(text, max_chars=3000)
    print(f"[OSOBA] {len(text.split())} words → {len(chunks)} chunks")
    parts = []
    for i, chunk in enumerate(chunks):
        print(f"[OSOBA] Chunk {i+1}/{len(chunks)}")
        data = await tts_chunk(chunk, voice)
        parts.append(data)
    # Concatenate raw MP3 bytes (works fine for sequential playback)
    return b"".join(parts)

@app.get("/", response_class=HTMLResponse)
def root():
    return (
        "<html><body style='font-family:monospace;background:#0a1628;color:#4f9fff;padding:40px'>"
        "<h2>OSOBA Voice-Over Studio</h2>"
        f"<p>Status: <b>ONLINE</b></p>"
        f"<p>Voice: <b>{VOICE}</b></p>"
        "<p>POST /generate — JSON {text, key, voice?}</p>"
        "<p>POST /generate-file — multipart {file .txt, key, voice?}</p>"
        "<p>GET  /voices — list available voices</p>"
        "</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "voice": VOICE}

@app.get("/voices")
def voices():
    return {"voices": VOICES, "default": VOICE}

@app.post("/generate")
async def generate(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if SECRET_KEY and body.get("key", "") != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    text  = body.get("text", "").strip()
    voice = body.get("voice", VOICE)
    if not text:
        raise HTTPException(400, "No text provided")
    if voice not in VOICES:
        voice = VOICE
    audio = await generate_audio(text, voice)
    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(audio).decode(),
        "format":  "mp3",
        "voice":   voice,
        "words":   len(text.split()),
        "chars":   len(text),
    })

@app.post("/generate-file")
async def generate_file(
    file:  UploadFile = File(...),
    key:   str = Form(default=""),
    voice: str = Form(default=""),
):
    if SECRET_KEY and key != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    if not file.filename.endswith(".txt"):
        raise HTTPException(400, "Only .txt files supported")
    content = await file.read()
    try:
        text = content.decode("utf-8").strip()
    except Exception:
        raise HTTPException(400, "File must be UTF-8 encoded text")
    if not text:
        raise HTTPException(400, "File is empty")
    if not voice or voice not in VOICES:
        voice = VOICE
    audio = await generate_audio(text, voice)
    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(audio).decode(),
        "format":  "mp3",
        "voice":   voice,
        "words":   len(text.split()),
        "chars":   len(text),
        "chunks":  len(split_chunks(text)),
    })
