import os, re, base64, asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
import edge_tts

VERSION    = "14.1.0"
SECRET_KEY = os.environ.get("OSOBA_SECRET", "osoba2026")
DEFAULT_VOICE = "en-US-GuyNeural"

SPEED_RATES = {
    "very_slow":     "-35%",
    "slow":          "-20%",
    "normal":        "+0%",
    "slightly_fast": "+15%",
    "fast":          "+30%",
}

VOICE_LABELS = {
    "en-US-GuyNeural":         "US Male — Smooth, Authoritative",
    "en-US-ChristopherNeural": "US Male — Rich, Professional",
    "en-US-EricNeural":        "US Male — Confident, Clear",
    "en-US-RogerNeural":       "US Male — Warm, Friendly",
    "en-US-SteffanNeural":     "US Male — Deep, Powerful",
    "en-US-AndrewNeural":      "US Male — Casual, Natural",
    "en-US-BrianNeural":       "US Male — Steady, Broadcast",
    "en-US-JennyNeural":       "US Female — Warm, Natural",
    "en-US-AriaNeural":        "US Female — Expressive, Lively",
    "en-US-MichelleNeural":    "US Female — Bright, Friendly",
    "en-US-AshleyNeural":      "US Female — Gentle, Soothing",
    "en-US-CoraNeural":        "US Female — Clear, Professional",
    "en-US-ElizabethNeural":   "US Female — Elegant, Polished",
    "en-US-AmberNeural":       "US Female — Casual, Upbeat",
    "en-US-AnaNeural":         "US Female — Youthful, Cheerful",
    "en-US-MonicaNeural":      "US Female — Mature, Confident",
    "en-US-NancyNeural":       "US Female — Composed, Assured",
    "en-US-SaraNeural":        "US Female — Soft, Sincere",
    "en-US-EmmaNeural":        "US Female — Warm, Expressive",
    "en-GB-RyanNeural":        "British Male — Deep, Cinematic",
    "en-GB-ThomasNeural":      "British Male — Clear, Documentary",
    "en-GB-AlfieNeural":       "British Male — Relaxed, Natural",
    "en-GB-ElliotNeural":      "British Male — Crisp, Educated",
    "en-GB-EthanNeural":       "British Male — Young, Engaging",
    "en-GB-NoahNeural":        "British Male — Calm, Measured",
    "en-GB-OliverNeural":      "British Male — Warm, Friendly",
    "en-GB-SoniaNeural":       "British Female — Crisp, Elegant",
    "en-GB-LibbyNeural":       "British Female — Light, Cheerful",
    "en-GB-MaisieNeural":      "British Female — Youthful, Bright",
    "en-GB-AbbiNeural":        "British Female — Clear, Confident",
    "en-GB-BellaNeural":       "British Female — Warm, Natural",
    "en-GB-HollieNeural":      "British Female — Smooth, Professional",
    "en-GB-OliviaNeural":      "British Female — Polished, Assured",
    "en-AU-WilliamNeural":     "Australian Male — Relaxed, Friendly",
    "en-AU-DarrenNeural":      "Australian Male — Direct, Clear",
    "en-AU-DuncanNeural":      "Australian Male — Steady, Natural",
    "en-AU-KenNeural":         "Australian Male — Warm, Casual",
    "en-AU-NeilNeural":        "Australian Male — Confident, Smooth",
    "en-AU-TimNeural":         "Australian Male — Laid-back, Easy",
    "en-AU-NatashaNeural":     "Australian Female — Warm, Natural",
    "en-AU-AnnetteNeural":     "Australian Female — Bright, Friendly",
    "en-AU-CarlyNeural":       "Australian Female — Crisp, Upbeat",
    "en-AU-ElsieNeural":       "Australian Female — Soft, Gentle",
    "en-AU-FreyaNeural":       "Australian Female — Energetic, Vivid",
    "en-AU-JoanneNeural":      "Australian Female — Calm, Assured",
    "en-AU-KimNeural":         "Australian Female — Soothing, Clear",
    "en-AU-TinaNeural":        "Australian Female — Cheerful, Lively",
    "en-NG-AbeoNeural":        "Nigerian Male 🇳🇬 — Rich, Authoritative",
    "en-NG-EzinneNeural":      "Nigerian Female 🇳🇬 — Warm, Expressive",
    "en-ZA-LukeNeural":        "South African Male 🇿🇦 — Deep, Distinct",
    "en-ZA-LeahNeural":        "South African Female 🇿🇦 — Clear, Vibrant",
    "en-IN-PrabhatNeural":     "Indian Male 🇮🇳 — Clear, Professional",
    "en-IN-NeerjaNeural":      "Indian Female 🇮🇳 — Warm, Expressive",
    "en-IE-ConnorNeural":      "Irish Male 🇮🇪 — Warm, Charming",
    "en-IE-EmilyNeural":       "Irish Female 🇮🇪 — Soft, Melodic",
    "en-CA-LiamNeural":        "Canadian Male 🇨🇦 — Warm, Natural",
    "en-CA-ClaraNeural":       "Canadian Female 🇨🇦 — Clear, Friendly",
    "en-NZ-MitchellNeural":    "New Zealand Male 🇳🇿 — Friendly, Casual",
    "en-NZ-MollyNeural":       "New Zealand Female 🇳🇿 — Bright, Natural",
    "en-PH-JamesNeural":       "Filipino Male 🇵🇭 — Clear, Engaging",
    "en-PH-RosaNeural":        "Filipino Female 🇵🇭 — Warm, Expressive",
    "en-SG-WayneNeural":       "Singaporean Male 🇸🇬 — Crisp, Modern",
    "en-SG-LunaNeural":        "Singaporean Female 🇸🇬 — Bright, Clear",
    "en-HK-SamNeural":         "Hong Kong Male 🇭🇰 — Confident, Clear",
    "en-HK-YanNeural":         "Hong Kong Female 🇭🇰 — Smooth, Natural",
}

# Runtime voice list — populated at startup by querying Microsoft directly
VOICES = {}

PREVIEW_TEXT = "Welcome to OptiToon Creations. Today we dive deep into the world of organized crime."


@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_voices()
    yield


app = FastAPI(lifespan=lifespan)


async def load_voices():
    global VOICES
    try:
        ms_voices = await edge_tts.list_voices()
        ms_ids    = {v["ShortName"] for v in ms_voices}
        VOICES    = {k: v for k, v in VOICE_LABELS.items() if k in ms_ids}
        print(f"[OSOBA v{VERSION}] Microsoft returned {len(ms_ids)} voices, {len(VOICES)} English matched")
    except Exception as e:
        VOICES = dict(VOICE_LABELS)
        print(f"[OSOBA v{VERSION}] WARNING: Voice list fetch failed ({e}), using full fallback")


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


async def tts_chunk(text, voice, rate, retries=3):
    """
    Use stream() instead of save() — avoids temp file I/O on Render's
    ephemeral disk and works with all edge-tts 6.x versions.
    """
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[OSOBA] attempt {attempt}/{retries} voice={voice} rate={rate} chars={len(text)}")
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            if audio_chunks:
                return b"".join(audio_chunks)
            last_error = "Empty audio stream from Microsoft"
            print(f"[OSOBA] empty audio on attempt {attempt}")
        except Exception as e:
            last_error = str(e)
            print(f"[OSOBA] attempt {attempt} error: {e}")
        if attempt < retries:
            await asyncio.sleep(2.0 * attempt)
    raise ValueError(f"No audio after {retries} attempts. Last error: {last_error}")


async def generate_audio(text, voice, speed_key="normal"):
    rate   = SPEED_RATES.get(speed_key, "+0%")
    chunks = split_chunks(text)
    print(f"[OSOBA] voice={voice} rate={rate} | words={len(text.split())} | chunks={len(chunks)}")
    parts  = []
    for i, chunk in enumerate(chunks):
        print(f"[OSOBA] processing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
        parts.append(await tts_chunk(chunk, voice, rate))
    return b"".join(parts), len(chunks)


@app.get("/", response_class=HTMLResponse)
def root():
    return (
        f"<html><body style='font-family:monospace;background:#0d0d0d;color:#1877f2;padding:40px'>"
        f"<h2>OSOBA Voice Studio v{VERSION}</h2>"
        f"<p style='color:#e8e8e8'>Status: <b style='color:#27ae60'>ONLINE</b></p>"
        f"<p style='color:#aaa'>{len(VOICES)} Microsoft-verified voices loaded</p>"
        f"</body></html>"
    )


@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "voice_count": len(VOICES)}


@app.get("/voices")
def list_voices_route():
    """Live Microsoft-verified voice list — used by the plugin"""
    return {"success": True, "voices": VOICES, "count": len(VOICES)}


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
        print(f"[OSOBA ERROR] voice={voice} | {e}")
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
    if voice not in VOICES:
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
