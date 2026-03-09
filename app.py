import os, re, base64, tempfile
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import edge_tts

app = FastAPI()

VERSION       = "13.0.0"
SECRET_KEY    = os.environ.get("OSOBA_SECRET", "osoba2026")
DEFAULT_VOICE = os.environ.get("OSOBA_VOICE",  "en-GB-RyanNeural")

SPEED_RATES = {
    "very_slow":     "-35%",
    "slow":          "-20%",
    "normal":        "+0%",
    "slightly_fast": "+15%",
    "fast":          "+30%",
}

# ── CONFIRMED WORKING voices only ──
# Removed: en-TZ (fails), en-KE (fails)
# Kept: en-US, en-GB, en-AU, en-CA, en-IE, en-IN, en-NZ, en-SG, en-HK, en-PH, en-NG, en-ZA
VOICES = {
    # US MALE (11)
    "en-US-GuyNeural":          "US Male — Smooth, Authoritative",
    "en-US-ChristopherNeural":  "US Male — Rich, Professional",
    "en-US-EricNeural":         "US Male — Confident, Clear",
    "en-US-RogerNeural":        "US Male — Warm, Friendly",
    "en-US-SteffanNeural":      "US Male — Deep, Powerful",
    "en-US-AndrewNeural":       "US Male — Casual, Natural",
    "en-US-BrianNeural":        "US Male — Steady, Broadcast",
    "en-US-DavisNeural":        "US Male — Smooth, Engaging",
    "en-US-JasonNeural":        "US Male — Bold, Charismatic",
    "en-US-TonyNeural":         "US Male — Sharp, Direct",
    "en-US-JacobNeural":        "US Male — Relaxed, Conversational",
    # US FEMALE (13)
    "en-US-JennyNeural":        "US Female — Warm, Natural",
    "en-US-AriaNeural":         "US Female — Expressive, Lively",
    "en-US-MichelleNeural":     "US Female — Bright, Friendly",
    "en-US-AshleyNeural":       "US Female — Gentle, Soothing",
    "en-US-CoraNeural":         "US Female — Clear, Professional",
    "en-US-ElizabethNeural":    "US Female — Elegant, Polished",
    "en-US-AmberNeural":        "US Female — Casual, Upbeat",
    "en-US-AnaNeural":          "US Female — Youthful, Cheerful",
    "en-US-MonicaNeural":       "US Female — Mature, Confident",
    "en-US-NancyNeural":        "US Female — Composed, Assured",
    "en-US-SaraNeural":         "US Female — Soft, Sincere",
    "en-US-EmmaNeural":         "US Female — Warm, Expressive",
    # BRITISH MALE (7)
    "en-GB-RyanNeural":         "British Male — Deep, Cinematic",
    "en-GB-ThomasNeural":       "British Male — Clear, Documentary",
    "en-GB-AlfieNeural":        "British Male — Relaxed, Natural",
    "en-GB-ElliotNeural":       "British Male — Crisp, Educated",
    "en-GB-EthanNeural":        "British Male — Young, Engaging",
    "en-GB-NoahNeural":         "British Male — Calm, Measured",
    "en-GB-OliverNeural":       "British Male — Warm, Friendly",
    # BRITISH FEMALE (7)
    "en-GB-SoniaNeural":        "British Female — Crisp, Elegant",
    "en-GB-LibbyNeural":        "British Female — Light, Cheerful",
    "en-GB-MaisieNeural":       "British Female — Youthful, Bright",
    "en-GB-AbbiNeural":         "British Female — Clear, Confident",
    "en-GB-BellaNeural":        "British Female — Warm, Natural",
    "en-GB-HollieNeural":       "British Female — Smooth, Professional",
    "en-GB-OliviaNeural":       "British Female — Polished, Assured",
    # AUSTRALIAN MALE (6)
    "en-AU-WilliamNeural":      "Australian Male — Relaxed, Friendly",
    "en-AU-DarrenNeural":       "Australian Male — Direct, Clear",
    "en-AU-DuncanNeural":       "Australian Male — Steady, Natural",
    "en-AU-KenNeural":          "Australian Male — Warm, Casual",
    "en-AU-NeilNeural":         "Australian Male — Confident, Smooth",
    "en-AU-TimNeural":          "Australian Male — Laid-back, Easy",
    # AUSTRALIAN FEMALE (8)
    "en-AU-NatashaNeural":      "Australian Female — Warm, Natural",
    "en-AU-AnnetteNeural":      "Australian Female — Bright, Friendly",
    "en-AU-CarlyNeural":        "Australian Female — Crisp, Upbeat",
    "en-AU-ElsieNeural":        "Australian Female — Soft, Gentle",
    "en-AU-FreyaNeural":        "Australian Female — Energetic, Vivid",
    "en-AU-JoanneNeural":       "Australian Female — Calm, Assured",
    "en-AU-KimNeural":          "Australian Female — Soothing, Clear",
    "en-AU-TinaNeural":         "Australian Female — Cheerful, Lively",
    # NIGERIAN (confirmed working)
    "en-NG-AbeoNeural":         "Nigerian Male — Rich, Authoritative",
    "en-NG-EzinneNeural":       "Nigerian Female — Warm, Expressive",
    # SOUTH AFRICAN (confirmed working)
    "en-ZA-LukeNeural":         "South African Male — Deep, Distinct",
    "en-ZA-LeahNeural":         "South African Female — Clear, Vibrant",
    # INDIAN
    "en-IN-PrabhatNeural":      "Indian Male — Clear, Professional",
    "en-IN-NeerjaNeural":       "Indian Female — Warm, Expressive",
    # IRISH
    "en-IE-ConnorNeural":       "Irish Male — Warm, Charming",
    "en-IE-EmilyNeural":        "Irish Female — Soft, Melodic",
    # CANADIAN
    "en-CA-LiamNeural":         "Canadian Male — Warm, Natural",
    "en-CA-ClaraNeural":        "Canadian Female — Clear, Friendly",
    # NEW ZEALAND
    "en-NZ-MitchellNeural":     "New Zealand Male — Friendly, Casual",
    "en-NZ-MollyNeural":        "New Zealand Female — Bright, Natural",
    # FILIPINO
    "en-PH-JamesNeural":        "Filipino Male — Clear, Engaging",
    "en-PH-RosaNeural":         "Filipino Female — Warm, Expressive",
    # SINGAPOREAN
    "en-SG-WayneNeural":        "Singaporean Male — Crisp, Modern",
    "en-SG-LunaNeural":         "Singaporean Female — Bright, Clear",
    # HONG KONG
    "en-HK-SamNeural":          "Hong Kong Male — Confident, Clear",
    "en-HK-YanNeural":          "Hong Kong Female — Smooth, Natural",
}

PREVIEW_TEXT = "Welcome to OptiToon Creations. Today we dive deep into the world of organized crime — the hierarchies, the rules, and the ruthless power struggles that defined history's most dangerous organizations."

print(f"[OSOBA v{VERSION}] READY — {len(VOICES)} confirmed voices")

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
        if not data:
            raise ValueError("No audio was received. Please verify that your parameters are correct.")
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
        f"<p style='color:#aaa'>{len(VOICES)} confirmed voices loaded</p>"
        f"<p style='color:#888'>GET /health &nbsp;|&nbsp; POST /generate &nbsp;|&nbsp; POST /preview</p>"
        f"</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "voice_count": len(VOICES), "speeds": list(SPEED_RATES.keys())}

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
