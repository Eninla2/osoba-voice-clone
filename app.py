import os, re, base64, asyncio, tempfile
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse
import edge_tts

app = FastAPI()

SECRET_KEY    = os.environ.get("OSOBA_SECRET", "osoba2026")
DEFAULT_VOICE = os.environ.get("OSOBA_VOICE", "en-GB-RyanNeural")

VOICES = {
    "en-GB-RyanNeural":        "British Male - Deep, Cinematic",
    "en-GB-ThomasNeural":      "British Male - Clear, Documentary",
    "en-US-GuyNeural":         "American Male - Smooth, Authoritative",
    "en-US-ChristopherNeural": "American Male - Rich, Professional",
    "en-GB-SoniaNeural":       "British Female - Crisp, Elegant",
    "en-US-JennyNeural":       "American Female - Warm, Natural",
    "en-US-AriaNeural":        "American Female - Expressive",
    "en-AU-NatashaNeural":     "Australian Female - Warm, Natural",
}

# Edge-TTS uses rate strings like "-20%" to slow down, "+20%" to speed up
SPEED_RATES = {
    "very_slow":     "-35%",
    "slow":          "-20%",
    "normal":        "+0%",
    "slightly_fast": "+15%",
    "fast":          "+30%",
}

print(f"[OSOBA] Edge TTS Voice Studio READY — default voice: {DEFAULT_VOICE}")

def split_chunks(text, max_chars=3000):
    paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip()
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
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
    return chunks if chunks else [text[:max_chars]]

async def tts_chunk(text, voice, rate):
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(tmp_path)
    with open(tmp_path, "rb") as f:
        data = f.read()
    os.unlink(tmp_path)
    return data

async def generate_audio(text, voice, speed_key="normal"):
    rate   = SPEED_RATES.get(speed_key, "+0%")
    chunks = split_chunks(text)
    print(f"[OSOBA] {len(text.split())} words | {len(chunks)} chunks | voice: {voice} | rate: {rate}")
    parts = []
    for i, chunk in enumerate(chunks):
        print(f"[OSOBA] Chunk {i+1}/{len(chunks)}: {len(chunk)} chars")
        parts.append(await tts_chunk(chunk, voice, rate))
    return b"".join(parts), len(chunks)

@app.get("/", response_class=HTMLResponse)
def root():
    vlist = "".join(f"<li>{k} — {v}</li>" for k, v in VOICES.items())
    slist = "".join(f"<li>{k} → {v}</li>" for k, v in SPEED_RATES.items())
    return (
        "<html><body style='font-family:monospace;background:#0a1628;color:#4f9fff;padding:40px'>"
        "<h2>OSOBA Voice-Over Studio</h2><p>Status: <b>ONLINE</b></p>"
        f"<p>Default Voice: <b>{DEFAULT_VOICE}</b></p>"
        f"<b>Voices:</b><ul>{vlist}</ul>"
        f"<b>Speeds:</b><ul>{slist}</ul>"
        "</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "voices": list(VOICES.keys()), "default": DEFAULT_VOICE}

@app.get("/voices")
def voices():
    return {"voices": VOICES, "default": DEFAULT_VOICE, "speeds": SPEED_RATES}

@app.post("/generate")
async def generate(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if SECRET_KEY and body.get("key", "") != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    text      = body.get("text", "").strip()
    voice     = body.get("voice", DEFAULT_VOICE)
    speed_key = body.get("speed", "normal")
    if not text:
        raise HTTPException(400, "No text provided")
    if voice not in VOICES:
        voice = DEFAULT_VOICE
    if speed_key not in SPEED_RATES:
        speed_key = "normal"
    try:
        audio, num_chunks = await generate_audio(text, voice, speed_key)
    except Exception as e:
        raise HTTPException(500, f"Generation error: {str(e)}")
    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(audio).decode(),
        "format":  "mp3",
        "voice":   voice,
        "speed":   speed_key,
        "words":   len(text.split()),
        "chars":   len(text),
        "chunks":  num_chunks,
    })

@app.post("/generate-file")
async def generate_file(
    file:      UploadFile = File(...),
    key:       str = Form(default=""),
    voice:     str = Form(default=""),
    speed:     str = Form(default="normal"),
):
    if SECRET_KEY and key != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    if not file.filename.lower().endswith(".txt"):
        raise HTTPException(400, "Only .txt files supported")
    content = await file.read()
    try:
        text = content.decode("utf-8").strip()
    except Exception:
        raise HTTPException(400, "File must be UTF-8 encoded plain text")
    if not text:
        raise HTTPException(400, "File is empty")
    if not voice or voice not in VOICES:
        voice = DEFAULT_VOICE
    if speed not in SPEED_RATES:
        speed = "normal"
    try:
        audio, num_chunks = await generate_audio(text, voice, speed)
    except Exception as e:
        raise HTTPException(500, f"Generation error: {str(e)}")
    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(audio).decode(),
        "format":  "mp3",
        "voice":   voice,
        "speed":   speed,
        "words":   len(text.split()),
        "chunks":  num_chunks,
    })
