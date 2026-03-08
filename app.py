import os, io, re, base64, asyncio, tempfile
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse

app = FastAPI()

SECRET_KEY     = os.environ.get("OSOBA_SECRET", "")
HF_TOKEN       = os.environ.get("HF_TOKEN", "")
REF_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "osoba_reference.wav")
REF_TEXT       = "Welcome to OptiToon Creations. Today we're diving deep into the world of organized crime — the hierarchies, the rules, and the ruthless power struggles that defined some of history's most dangerous organizations. Stay with me, because this story goes deeper than you think."

print("[OSOBA] Loading reference audio...")
with open(REF_AUDIO_PATH, "rb") as f:
    REF_AUDIO_B64 = base64.b64encode(f.read()).decode()
print(f"[OSOBA] Voice Clone Proxy READY. HF_TOKEN={'SET' if HF_TOKEN else 'MISSING'}")

# F5-TTS spaces to try in order (with auth)
F5_SPACES = [
    ("mrfakename/E2-F5-TTS", "/basic_tts"),
    ("mrfakename/E2-F5-TTS", "/infer"),
    ("ylacombe/f5-tts",      "/basic_tts"),
]

def split_chunks(text: str, max_chars: int = 800) -> list:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip()
        else:
            if current: chunks.append(current)
            current = s[:max_chars]
    if current: chunks.append(current)
    return chunks or [text[:max_chars]]

def generate_chunk_f5(text_chunk: str) -> bytes:
    """Try F5-TTS spaces with HF token auth."""
    from gradio_client import Client, handle_file

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(base64.b64decode(REF_AUDIO_B64))
        tmp_path = tmp.name

    last_err = None
    for space_id, api_name in F5_SPACES:
        try:
            print(f"[OSOBA] Trying {space_id} → {api_name}")
            client = Client(space_id, hf_token=HF_TOKEN if HF_TOKEN else None)
            result = client.predict(
                ref_audio_input = handle_file(tmp_path),
                ref_text_input  = REF_TEXT,
                gen_text_input  = text_chunk,
                remove_silence  = True,
                api_name        = api_name,
            )
            audio_path = result[0] if isinstance(result, (list, tuple)) else result
            with open(audio_path, "rb") as f:
                data = f.read()
            os.unlink(tmp_path)
            print(f"[OSOBA] Success with {space_id}")
            return data
        except Exception as e:
            print(f"[OSOBA] {space_id} failed: {e}")
            last_err = e
            continue

    os.unlink(tmp_path)
    raise RuntimeError(f"All F5-TTS spaces failed: {last_err}")

import soundfile as sf
import numpy as np

def concat_wav(wav_chunks: list) -> bytes:
    arrays, sr = [], 24000
    for cb in wav_chunks:
        try:
            data, sr = sf.read(io.BytesIO(cb))
            arrays.append(data)
        except Exception:
            continue
    if not arrays: raise ValueError("No valid audio chunks")
    out = io.BytesIO()
    sf.write(out, np.concatenate(arrays), sr, format="WAV")
    out.seek(0)
    return out.read()

async def _process(text: str):
    chunks     = split_chunks(text)
    word_count = len(text.split())
    print(f"[OSOBA] {word_count} words → {len(chunks)} chunks")
    wav_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"[OSOBA] Chunk {i+1}/{len(chunks)}")
        data = await asyncio.get_event_loop().run_in_executor(
            None, generate_chunk_f5, chunk
        )
        wav_chunks.append(data)
    final = concat_wav(wav_chunks)
    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(final).decode(),
        "format":  "wav",
        "voice":   "OSOBA_KEHINDE_CLONE",
        "words":   word_count,
        "chunks":  len(chunks),
        "chars":   len(text),
    })

@app.get("/", response_class=HTMLResponse)
def root():
    token_status = "SET" if HF_TOKEN else "MISSING — add HF_TOKEN env var"
    return (
        "<html><body style='font-family:monospace;background:#0a1628;color:#4f9fff;padding:40px'>"
        "<h2>OSOBA Voice Clone Studio</h2>"
        "<p>Status: <b>ONLINE</b></p>"
        f"<p>HF Token: <b>{token_status}</b></p>"
        "<p>Voice: <b>OSOBA KEHINDE CLONE</b></p>"
        "</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "voice": "OSOBA_KEHINDE_CLONE", "hf_token": bool(HF_TOKEN)}

@app.post("/generate")
async def generate(request: Request):
    try: body = await request.json()
    except: raise HTTPException(400, "Invalid JSON")
    if SECRET_KEY and body.get("key","") != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    text = body.get("text","").strip()
    if not text: raise HTTPException(400, "No text provided")
    if not HF_TOKEN: raise HTTPException(500, "HF_TOKEN not set on server. Add it in Render environment variables.")
    return await _process(text)

@app.post("/generate-file")
async def generate_file(file: UploadFile = File(...), key: str = Form(default="")):
    if SECRET_KEY and key != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    if not file.filename.endswith(".txt"):
        raise HTTPException(400, "Only .txt files supported")
    content = await file.read()
    try: text = content.decode("utf-8").strip()
    except: raise HTTPException(400, "File must be UTF-8 encoded")
    if not text: raise HTTPException(400, "File is empty")
    if not HF_TOKEN: raise HTTPException(500, "HF_TOKEN not set on server.")
    return await _process(text)
