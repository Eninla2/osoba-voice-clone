import os, re, base64, tempfile
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import edge_tts

app = FastAPI()

VERSION       = "11.0.0"
SECRET_KEY    = os.environ.get("OSOBA_SECRET", "osoba2026")
DEFAULT_VOICE = os.environ.get("OSOBA_VOICE",  "en-GB-RyanNeural")

SPEED_RATES = {
    "very_slow":     "-35%",
    "slow":          "-20%",
    "normal":        "+0%",
    "slightly_fast": "+15%",
    "fast":          "+30%",
}

PREVIEW_TEXT = "Welcome to OptiToon Creations. Today we dive deep into the world of organized crime — the hierarchies, the rules, and the ruthless power struggles that defined history's most dangerous organizations."

# All accepted voice IDs — any edge_tts voice string is valid
VALID_VOICE_RE = re.compile(r'^[a-z]{2}-[A-Z]{2,3}-[A-Za-z]+Neural$')

def is_valid_voice(v):
    return bool(VALID_VOICE_RE.match(str(v)))

print(f"[OSOBA v{VERSION}] READY — default voice: {DEFAULT_VOICE}")

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
    try:
        await edge_tts.Communicate(text, voice, rate=rate).save(tmp_path)
        with open(tmp_path, "rb") as f:
            data = f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
    return data

async def generate_audio(text, voice, speed_key="normal"):
    rate   = SPEED_RATES.get(speed_key, "+0%")
    chunks = split_chunks(text)
    print(f"[OSOBA] voice={voice} | words={len(text.split())} | chunks={len(chunks)} | rate={rate}")
    parts = []
    for i, chunk in enumerate(chunks):
        print(f"[OSOBA] chunk {i+1}/{len(chunks)}")
        parts.append(await tts_chunk(chunk, voice, rate))
    return b"".join(parts), len(chunks)

@app.get("/", response_class=HTMLResponse)
def root():
    return (
        f"<html><body style='font-family:monospace;background:#0d0d0d;color:#1877f2;padding:40px'>"
        f"<h2>OSOBA Voice Studio v{VERSION}</h2>"
        f"<p style='color:#e8e8e8'>Status: <b style='color:#27ae60'>ONLINE</b></p>"
        f"<p style='color:#888'>Endpoints: GET /health | POST /generate | POST /preview</p>"
        f"<p style='color:#888'>Accepts any valid Edge TTS voice string.</p>"
        f"</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "default_voice": DEFAULT_VOICE, "speeds": list(SPEED_RATES.keys())}

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
    # Accept any valid voice string — do NOT silently replace
    if not is_valid_voice(voice):
        voice = DEFAULT_VOICE
    if speed_key not in SPEED_RATES:
        speed_key = "normal"
    try:
        audio, num_chunks = await generate_audio(text, voice, speed_key)
    except Exception as e:
        print(f"[OSOBA ERROR] {e}")
        raise HTTPException(500, f"TTS error: {str(e)}")
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

@app.post("/preview")
async def preview_voice(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if SECRET_KEY and body.get("key", "") != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    voice = body.get("voice", DEFAULT_VOICE)
    if not is_valid_voice(voice):
        voice = DEFAULT_VOICE
    try:
        audio = await tts_chunk(PREVIEW_TEXT, voice, "+0%")
    except Exception as e:
        raise HTTPException(500, f"Preview error: {str(e)}")
    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(audio).decode(),
        "format":  "mp3",
        "voice":   voice,
    })
