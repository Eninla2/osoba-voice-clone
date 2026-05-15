"""
OSOBA VOICE STUDIO — Render Server v15.0  (100% FREE)
OptiToon Creations

Engine  : Microsoft Edge TTS — no API key, no billing, no limits
Voices  : ALL available Microsoft Neural voices (400+) fetched live at startup
Styles  : Full SSML style support (newscast, narration, cheerful, angry, etc.)
Languages: All Microsoft-supported languages

Render start command: uvicorn app:app --host 0.0.0.0 --port $PORT

ENV VARS (Render dashboard):
  OSOBA_SECRET  — must match the Secret Key in your WP plugin settings
  PORT          — Render sets this automatically
"""

import os, re, base64, asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from contextlib import asynccontextmanager
import edge_tts

VERSION       = "15.1.0"
SECRET_KEY    = os.environ.get("OSOBA_SECRET", "osoba2026")

USER_KEYS = [k.strip() for k in os.environ.get("USER_KEYS", "").split(",") if k.strip()]

def is_valid_key(key: str) -> bool:
    if not key: return False
    if SECRET_KEY and key == SECRET_KEY: return True
    if USER_KEYS: return key in USER_KEYS
    if not SECRET_KEY and not USER_KEYS: return True
    return False
DEFAULT_VOICE = "en-US-GuyNeural"

SPEED_RATES = {
    "very_slow":     "-35%",
    "slow":          "-20%",
    "normal":        "+0%",
    "slightly_fast": "+15%",
    "fast":          "+30%",
}

# Voices that support SSML express-as styles in Edge TTS
# style → human label
STYLE_LABELS = {
    "advertisement_upbeat":       "Advertisement Upbeat",
    "affectionate":               "Affectionate",
    "angry":                      "Angry",
    "assistant":                  "Assistant",
    "calm":                       "Calm",
    "chat":                       "Chat",
    "cheerful":                   "Cheerful",
    "customerservice":            "Customer Service",
    "depressed":                  "Depressed",
    "disgruntled":                "Disgruntled",
    "documentary-narration":      "Documentary Narration",
    "embarrassed":                "Embarrassed",
    "empathetic":                 "Empathetic",
    "envious":                    "Envious",
    "excited":                    "Excited",
    "fearful":                    "Fearful",
    "friendly":                   "Friendly",
    "gentle":                     "Gentle",
    "hopeful":                    "Hopeful",
    "lyrical":                    "Lyrical",
    "narration-professional":     "Narration Professional",
    "narration-relaxed":          "Narration Relaxed",
    "newscast":                   "Newscast",
    "newscast-casual":            "Newscast Casual",
    "newscast-formal":            "Newscast Formal",
    "poetry-reading":             "Poetry Reading",
    "sad":                        "Sad",
    "serious":                    "Serious",
    "shouting":                   "Shouting",
    "sports_commentary":          "Sports Commentary",
    "sports_commentary_excited":  "Sports Commentary Excited",
    "whispering":                 "Whispering",
    "terrified":                  "Terrified",
    "unfriendly":                 "Unfriendly",
}

# Populated at startup from Microsoft's live voice list
VOICES      = {}   # voice_id → display label
VOICE_META  = {}   # voice_id → full metadata dict from Microsoft
VOICE_STYLES = {}  # voice_id → list of supported style keys

PREVIEW_TEXT = "Welcome to OptiToon Creations Voice Studio. This is a preview of the selected voice."


# ── STARTUP ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await _load_all_voices()
    yield


app = FastAPI(lifespan=lifespan)


async def _load_all_voices():
    """Load only the 36 original verified working voices."""
    global VOICES, VOICE_META, VOICE_STYLES
    VOICES = {
        # US MALE (7)
        "en-US-GuyNeural":         "US Male — Smooth, Authoritative",
        "en-US-ChristopherNeural": "US Male — Rich, Professional",
        "en-US-EricNeural":        "US Male — Confident, Clear",
        "en-US-RogerNeural":       "US Male — Warm, Friendly",
        "en-US-SteffanNeural":     "US Male — Deep, Powerful",
        "en-US-AndrewNeural":      "US Male — Casual, Natural",
        "en-US-BrianNeural":       "US Male — Steady, Broadcast",
        # US FEMALE (3)
        "en-US-JennyNeural":       "US Female — Warm, Natural",
        "en-US-AriaNeural":        "US Female — Expressive, Lively",
        "en-US-EmmaNeural":        "US Female — Warm, Expressive",
        # BRITISH MALE (7)
        "en-GB-RyanNeural":        "British Male — Deep, Cinematic",
        "en-GB-ThomasNeural":      "British Male — Clear, Documentary",
        # BRITISH FEMALE (7)
        "en-GB-SoniaNeural":       "British Female — Crisp, Elegant",
        "en-GB-LibbyNeural":       "British Female — Light, Cheerful",
        "en-GB-MaisieNeural":      "British Female — Youthful, Bright",
        # AUSTRALIAN (2)
        "en-AU-WilliamNeural":     "Australian Male — Relaxed, Friendly",
        "en-AU-NatashaNeural":     "Australian Female — Warm, Natural",
        # NIGERIAN (2)
        "en-NG-AbeoNeural":        "Nigerian Male \U0001f1f3\U0001f1ec — Rich, Authoritative",
        "en-NG-EzinneNeural":      "Nigerian Female \U0001f1f3\U0001f1ec — Warm, Expressive",
        # SOUTH AFRICAN (2)
        "en-ZA-LukeNeural":        "South African Male \U0001f1ff\U0001f1e6 — Deep, Distinct",
        "en-ZA-LeahNeural":        "South African Female \U0001f1ff\U0001f1e6 — Clear, Vibrant",
        # INDIAN (2)
        "en-IN-PrabhatNeural":     "Indian Male \U0001f1ee\U0001f1f3 — Clear, Professional",
        "en-IN-NeerjaNeural":      "Indian Female \U0001f1ee\U0001f1f3 — Warm, Expressive",
        # IRISH (2)
        "en-IE-ConnorNeural":      "Irish Male \U0001f1ee\U0001f1ea — Warm, Charming",
        "en-IE-EmilyNeural":       "Irish Female \U0001f1ee\U0001f1ea — Soft, Melodic",
        # CANADIAN (2)
        "en-CA-LiamNeural":        "Canadian Male \U0001f1e8\U0001f1e6 — Warm, Natural",
        "en-CA-ClaraNeural":       "Canadian Female \U0001f1e8\U0001f1e6 — Clear, Friendly",
        # ── MULTILINGUAL VOICES (for dubbing) ──
        # French
        "fr-FR-HenriNeural":       "French Male — Standard",
        "fr-FR-DeniseNeural":      "French Female — Expressif",
        # Spanish
        "es-ES-AlvaroNeural":      "Spanish Male — Claro",
        "es-ES-ElviraNeural":      "Spanish Female — Cálida",
        # Portuguese (Brazil)
        "pt-BR-AntonioNeural":     "Portuguese Male — Natural",
        "pt-BR-FranciscaNeural":   "Portuguese Female — Amigável",
        # Arabic
        "ar-SA-HamedNeural":       "Arabic Male — Fusha",
        "ar-SA-ZariyahNeural":     "Arabic Female — Soft",
        # Hindi
        "hi-IN-MadhurNeural":      "Hindi Male — Clear",
        "hi-IN-SwaraNeural":       "Hindi Female — Natural",
        # German
        "de-DE-ConradNeural":      "German Male — Klar",
        "de-DE-KatjaNeural":       "German Female — Freundlich",
        # ── EXTRA ENGLISH VOICES (added to match WordPress dropdown) ──
        # US Male extra
        "en-US-DavisNeural":       "US Male — Davis, Deep",
        "en-US-TonyNeural":        "US Male — Tony, Casual",
        "en-US-BrandonNeural":     "US Male — Brandon, Youthful",
        # US Female extra
        "en-US-JaneNeural":        "US Female — Jane, Natural",
        "en-US-NancyNeural":       "US Female — Nancy, Soft",
        "en-US-MichelleNeural":    "US Female — Michelle, Friendly",
        "en-US-CoraNeural":        "US Female — Cora, Calm",
        "en-US-ElizabethNeural":   "US Female — Elizabeth, Elegant",
        # British Male extra
        "en-GB-OllieNeural":       "British Male — Ollie, Friendly",
        "en-GB-AlfieNeural":       "British Male — Alfie, Warm",
        "en-GB-ElliotNeural":      "British Male — Elliot, Clear",
        "en-GB-EthanNeural":       "British Male — Ethan, Deep",
        "en-GB-NoahNeural":        "British Male — Noah, Warm",
        "en-GB-OliverNeural":      "British Male — Oliver, Friendly",
        # British Female extra
        "en-GB-AbbiNeural":        "British Female — Abbi, Natural",
        "en-GB-BellaNeural":       "British Female — Bella, Soft",
        "en-GB-HollieNeural":      "British Female — Hollie, Bright",
        "en-GB-OliviaNeural":      "British Female — Olivia, Elegant",
        # Australian extra
        "en-AU-DarrenNeural":      "Australian Male — Darren, Relaxed",
        "en-AU-AnnetteNeural":     "Australian Female — Annette, Bright",
        "en-AU-CarlyNeural":       "Australian Female — Carly, Warm",
        # Filipino
        "en-PH-JamesNeural":       "Filipino Male \U0001f1f5\U0001f1ed — James, Clear",
        "en-PH-RosaNeural":        "Filipino Female \U0001f1f5\U0001f1ed — Rosa, Warm",
        # Singapore
        "en-SG-WayneNeural":       "Singapore Male \U0001f1f8\U0001f1ec — Wayne, Precise",
        "en-SG-LunaNeural":        "Singapore Female \U0001f1f8\U0001f1ec — Luna, Friendly",
    }
    VOICE_META   = {}
    VOICE_STYLES = {}
    print(f"[OVS v{VERSION}] {len(VOICES)} verified working voices loaded")


def _locale_label(locale: str) -> str:
    """Convert locale code to human-readable language/region label."""
    MAP = {
        "en-US": "US English",
        "en-GB": "British English",
        "en-AU": "Australian English",
        "en-CA": "Canadian English",
        "en-IE": "Irish English",
        "en-IN": "Indian English",
        "en-NZ": "New Zealand English",
        "en-NG": "Nigerian English 🇳🇬",
        "en-ZA": "South African English 🇿🇦",
        "en-GH": "Ghanaian English 🇬🇭",
        "en-KE": "Kenyan English 🇰🇪",
        "en-TZ": "Tanzanian English 🇹🇿",
        "en-PH": "Filipino English 🇵🇭",
        "en-SG": "Singaporean English 🇸🇬",
        "en-HK": "Hong Kong English 🇭🇰",
        "fr-FR": "French 🇫🇷",
        "fr-CA": "Canadian French 🇨🇦",
        "es-ES": "Spanish 🇪🇸",
        "es-MX": "Mexican Spanish 🇲🇽",
        "es-US": "US Spanish",
        "de-DE": "German 🇩🇪",
        "it-IT": "Italian 🇮🇹",
        "pt-BR": "Brazilian Portuguese 🇧🇷",
        "pt-PT": "Portuguese 🇵🇹",
        "ar-EG": "Arabic Egyptian 🇪🇬",
        "ar-SA": "Arabic Saudi 🇸🇦",
        "zh-CN": "Chinese Mandarin 🇨🇳",
        "zh-TW": "Chinese Taiwanese 🇹🇼",
        "zh-HK": "Chinese Cantonese 🇭🇰",
        "ja-JP": "Japanese 🇯🇵",
        "ko-KR": "Korean 🇰🇷",
        "hi-IN": "Hindi 🇮🇳",
        "yo-NG": "Yoruba 🇳🇬",
        "ig-NG": "Igbo 🇳🇬",
        "ha-NG": "Hausa 🇳🇬",
        "sw-KE": "Swahili 🇰🇪",
        "sw-TZ": "Swahili Tanzania 🇹🇿",
        "ru-RU": "Russian 🇷🇺",
        "tr-TR": "Turkish 🇹🇷",
        "pl-PL": "Polish 🇵🇱",
        "nl-NL": "Dutch 🇳🇱",
        "sv-SE": "Swedish 🇸🇪",
        "da-DK": "Danish 🇩🇰",
        "nb-NO": "Norwegian 🇳🇴",
        "fi-FI": "Finnish 🇫🇮",
        "cs-CZ": "Czech 🇨🇿",
        "ro-RO": "Romanian 🇷🇴",
        "hu-HU": "Hungarian 🇭🇺",
        "el-GR": "Greek 🇬🇷",
        "he-IL": "Hebrew 🇮🇱",
        "id-ID": "Indonesian 🇮🇩",
        "ms-MY": "Malay 🇲🇾",
        "th-TH": "Thai 🇹🇭",
        "vi-VN": "Vietnamese 🇻🇳",
        "uk-UA": "Ukrainian 🇺🇦",
        "bg-BG": "Bulgarian 🇧🇬",
        "hr-HR": "Croatian 🇭🇷",
        "sk-SK": "Slovak 🇸🇰",
        "sl-SI": "Slovenian 🇸🇮",
        "lt-LT": "Lithuanian 🇱🇹",
        "lv-LV": "Latvian 🇱🇻",
        "et-EE": "Estonian 🇪🇪",
        "af-ZA": "Afrikaans 🇿🇦",
        "am-ET": "Amharic 🇪🇹",
        "bn-BD": "Bangla Bangladesh 🇧🇩",
        "bn-IN": "Bangla India 🇮🇳",
        "gu-IN": "Gujarati 🇮🇳",
        "kn-IN": "Kannada 🇮🇳",
        "ml-IN": "Malayalam 🇮🇳",
        "mr-IN": "Marathi 🇮🇳",
        "ta-IN": "Tamil India 🇮🇳",
        "ta-SG": "Tamil Singapore 🇸🇬",
        "ta-LK": "Tamil Sri Lanka 🇱🇰",
        "te-IN": "Telugu 🇮🇳",
        "ur-IN": "Urdu India 🇮🇳",
        "ur-PK": "Urdu Pakistan 🇵🇰",
        "uz-UZ": "Uzbek 🇺🇿",
        "fa-IR": "Persian 🇮🇷",
        "ka-GE": "Georgian 🇬🇪",
        "az-AZ": "Azerbaijani 🇦🇿",
        "kk-KZ": "Kazakh 🇰🇿",
        "mn-MN": "Mongolian 🇲🇳",
        "my-MM": "Burmese 🇲🇲",
        "km-KH": "Khmer 🇰🇭",
        "lo-LA": "Lao 🇱🇦",
        "si-LK": "Sinhala 🇱🇰",
        "ne-NP": "Nepali 🇳🇵",
        "ps-AF": "Pashto 🇦🇫",
        "so-SO": "Somali 🇸🇴",
        "zu-ZA": "Zulu 🇿🇦",
        "jv-ID": "Javanese 🇮🇩",
        "su-ID": "Sundanese 🇮🇩",
        "fil-PH": "Filipino 🇵🇭",
        "gl-ES": "Galician 🇪🇸",
        "eu-ES": "Basque 🇪🇸",
        "ca-ES": "Catalan 🇪🇸",
        "cy-GB": "Welsh 🏴󠁧󠁢󠁷󠁬󠁳󠁿",
        "ga-IE": "Irish 🇮🇪",
        "mt-MT": "Maltese 🇲🇹",
        "is-IS": "Icelandic 🇮🇸",
        "mk-MK": "Macedonian 🇲🇰",
        "sq-AL": "Albanian 🇦🇱",
        "sr-RS": "Serbian 🇷🇸",
        "bs-BA": "Bosnian 🇧🇦",
    }
    return MAP.get(locale, locale)


# ── TEXT CHUNKER ──────────────────────────────────────────────────────────

def _split_chunks(text: str, max_chars: int = 3000) -> list:
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


# ── TTS CORE ──────────────────────────────────────────────────────────────

def _build_ssml(text: str, voice: str, rate: str, style: str = "") -> str:
    """Build SSML markup. Uses express-as style if provided and supported."""
    meta      = VOICE_META.get(voice, {})
    locale    = meta.get("Locale", "en-US")
    # Escape special XML characters in text
    safe_text = (text
                 .replace("&", "&amp;")
                 .replace("<", "&lt;")
                 .replace(">", "&gt;")
                 .replace('"', "&quot;"))

    if style and style in (VOICE_STYLES.get(voice, [])):
        return (
            f"<speak version='1.0' "
            f"xmlns='http://www.w3.org/2001/10/synthesis' "
            f"xmlns:mstts='https://www.w3.org/2001/mstts' "
            f"xml:lang='{locale}'>"
            f"<voice name='{voice}'>"
            f"<mstts:express-as style='{style}'>"
            f"<prosody rate='{rate}'>{safe_text}</prosody>"
            f"</mstts:express-as>"
            f"</voice></speak>"
        )
    else:
        return (
            f"<speak version='1.0' "
            f"xmlns='http://www.w3.org/2001/10/synthesis' "
            f"xml:lang='{locale}'>"
            f"<voice name='{voice}'>"
            f"<prosody rate='{rate}'>{safe_text}</prosody>"
            f"</voice></speak>"
        )


async def _tts_chunk(text: str, voice: str, rate: str,
                     style: str = "", retries: int = 3) -> bytes:
    """Stream audio from Microsoft using plain text — no SSML."""
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            print(f"[OVS] attempt {attempt}/{retries}  voice={voice}  chars={len(text)}")
            # edge_tts only accepts plain text — SSML causes tags to be read aloud
            communicate  = edge_tts.Communicate(text, voice, rate=rate)
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            if audio_chunks:
                return b"".join(audio_chunks)
            last_error = "Empty audio stream from Microsoft"
            print(f"[OVS] empty stream on attempt {attempt}")
        except Exception as e:
            last_error = str(e)
            print(f"[OVS] attempt {attempt} error: {e}")
        if attempt < retries:
            await asyncio.sleep(2.0 * attempt)
    raise ValueError(f"No audio after {retries} attempts. Last: {last_error}")


async def _generate_audio(text: str, voice: str,
                           speed_key: str = "normal",
                           style: str = ""):
    rate   = SPEED_RATES.get(speed_key, "+0%")
    chunks = _split_chunks(text)
    print(f"[OVS] voice={voice}  rate={rate}  style={style or 'none'}  "
          f"words={len(text.split())}  chunks={len(chunks)}")
    parts = []
    for i, chunk in enumerate(chunks):
        print(f"[OVS] chunk {i+1}/{len(chunks)}  ({len(chunk)} chars)")
        parts.append(await _tts_chunk(chunk, voice, rate, style))
    return b"".join(parts), len(chunks)


# ── ROUTES ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    english = sum(1 for v in VOICES if v.startswith("en-"))
    return (
        "<html><body style='font-family:monospace;background:#0d0d0d;"
        "color:#1877f2;padding:40px'>"
        f"<h2>🎙 OSOBA Voice Studio v{VERSION}</h2>"
        "<p style='color:#e8e8e8'>Status: <b style='color:#27ae60'>ONLINE</b></p>"
        "<p style='color:#aaa'>Engine: Microsoft Edge TTS (100% FREE)</p>"
        f"<p style='color:#aaa'>{len(VOICES)} total voices "
        f"({english} English) loaded</p>"
        f"<p style='color:#aaa'>{len(VOICE_STYLES)} voices with style support</p>"
        "</body></html>"
    )


@app.api_route("/health", methods=["GET","HEAD"])
def health():
    english = sum(1 for v in VOICES if v.startswith("en-"))
    return {
        "status":        "ok",
        "version":       VERSION,
        "engine":        "Microsoft Edge TTS (FREE)",
        "voice_count":   len(VOICES),
        "english_count": english,
        "style_count":   len(VOICE_STYLES),
    }


@app.api_route("/ping", methods=["GET","HEAD"])
def ping():
    return {"pong": True}


@app.get("/voices")
def voices_route(lang: str = ""):
    """
    Returns all voices. Optional ?lang= filter e.g. ?lang=en for English only,
    ?lang=fr for French, ?lang=yo for Yoruba, etc.
    """
    if lang:
        filtered = {k: v for k, v in VOICES.items()
                    if k.lower().startswith(lang.lower())}
        return {"success": True, "voices": filtered, "count": len(filtered)}
    return {"success": True, "voices": VOICES, "count": len(VOICES)}


@app.get("/voices/english")
def voices_english():
    """Shortcut — English voices only."""
    filtered = {k: v for k, v in VOICES.items() if k.startswith("en-")}
    return {"success": True, "voices": filtered, "count": len(filtered)}


@app.get("/styles")
def styles_route():
    """Returns all supported styles and which voices support them."""
    return {
        "success":      True,
        "style_labels": STYLE_LABELS,
        "voice_styles": VOICE_STYLES,
    }


@app.get("/styles/{voice_id:path}")
def styles_for_voice(voice_id: str):
    """Returns styles supported by a specific voice."""
    supported = VOICE_STYLES.get(voice_id, [])
    return {
        "success":  True,
        "voice":    voice_id,
        "styles":   supported,
        "labels":   {s: STYLE_LABELS.get(s, s) for s in supported},
    }


@app.post("/generate")
async def generate(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if not is_valid_key(body.get("key", "")):
        raise HTTPException(403, "Invalid key")

    text      = body.get("text", "").strip()
    voice     = body.get("voice", DEFAULT_VOICE)
    speed_key = body.get("speed", "normal")
    style     = body.get("style", "").strip().lower()

    if not text:
        raise HTTPException(400, "No text provided")
    if len(text) > 100000:
        raise HTTPException(400, "Text too long (max 100,000 chars)")
    if voice not in VOICES:
        print(f"[OVS] Unknown voice '{voice}', falling back to {DEFAULT_VOICE}")
        voice = DEFAULT_VOICE
    if speed_key not in SPEED_RATES:
        speed_key = "normal"
    # Validate style — ignore unknown styles silently
    if style and style not in VOICE_STYLES.get(voice, []):
        print(f"[OVS] Style '{style}' not supported by {voice}, ignoring")
        style = ""

    try:
        audio, num_chunks = await _generate_audio(text, voice, speed_key, style)
    except Exception as e:
        print(f"[OVS ERROR] {e}")
        raise HTTPException(500, f"TTS error: {str(e)}")

    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(audio).decode(),
        "format":  "mp3",
        "voice":   voice,
        "speed":   speed_key,
        "style":   style or "default",
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
    if not is_valid_key(body.get("key", "")):
        raise HTTPException(403, "Invalid key")

    voice = body.get("voice", DEFAULT_VOICE)
    style = body.get("style", "").strip().lower()

    if voice not in VOICES:
        voice = DEFAULT_VOICE
    if style and style not in VOICE_STYLES.get(voice, []):
        style = ""

    try:
        audio = await _tts_chunk(PREVIEW_TEXT, voice, "+0%", style)
    except Exception as e:
        raise HTTPException(500, f"Preview error: {str(e)}")

    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(audio).decode(),
        "format":  "mp3",
        "voice":   voice,
        "style":   style or "default",
    })
