import os
import io
import re
import base64
import tempfile
import asyncio
import soundfile as sf
import numpy as np
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, HTMLResponse

app = FastAPI()

SECRET_KEY = os.environ.get("OSOBA_SECRET", "")
REF_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "osoba_reference.wav")
REF_TEXT = "Welcome to OptiToon Creations. Today we're diving deep into the world of organized crime — the hierarchies, the rules, and the ruthless power struggles that defined some of history's most dangerous organizations. Stay with me, because this story goes deeper than you think."

print("[OSOBA] Loading reference audio...")
with open(REF_AUDIO_PATH, "rb") as f:
    REF_AUDIO_B64 = base64.b64encode(f.read()).decode()
print("[OSOBA] Voice Clone Proxy READY.")

def split_into_chunks(text: str, max_chars: int = 800) -> list:
    """Split text into sentence-aware chunks for TTS generation."""
    # Split on sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # If single sentence is too long, split on commas
            if len(sentence) > max_chars:
                parts = sentence.split(", ")
                cur = ""
                for part in parts:
                    if len(cur) + len(part) + 2 <= max_chars:
                        cur = (cur + ", " + part).strip(", ")
                    else:
                        if cur:
                            chunks.append(cur)
                        cur = part
                if cur:
                    chunks.append(cur)
            else:
                current = sentence
    if current:
        chunks.append(current)
    return chunks

def generate_chunk(text_chunk: str) -> bytes:
    """Generate audio for one chunk via public F5-TTS space."""
    from gradio_client import Client, handle_file

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(base64.b64decode(REF_AUDIO_B64))
        tmp_path = tmp.name

    try:
        client = Client("mrfakename/E2-F5-TTS")
        result = client.predict(
            ref_audio_input=handle_file(tmp_path),
            ref_text_input=REF_TEXT,
            gen_text_input=text_chunk,
            remove_silence=True,
            api_name="/basic_tts"
        )
        audio_path = result[0] if isinstance(result, (list, tuple)) else result
        with open(audio_path, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp_path)

def concatenate_wav_bytes(wav_chunks: list) -> bytes:
    """Merge multiple WAV byte strings into one."""
    arrays = []
    sr = 24000
    for chunk_bytes in wav_chunks:
        buf = io.BytesIO(chunk_bytes)
        data, sr = sf.read(buf)
        arrays.append(data)
    full = np.concatenate(arrays)
    out = io.BytesIO()
    sf.write(out, full, sr, format="WAV")
    out.seek(0)
    return out.read()

@app.get("/", response_class=HTMLResponse)
def root():
    return (
        "<html><body style='font-family:monospace;background:#0a1628;color:#4f9fff;padding:40px'>"
        "<h2>🎙 OSOBA Voice Clone Studio</h2>"
        "<p>Status: <b>ONLINE</b></p>"
        "<p>Voice: <b>OSOBA KEHINDE CLONE (Enhanced)</b></p>"
        "<hr>"
        "<p><b>POST /generate</b> — JSON body: {\"text\":\"...\",\"key\":\"...\"} — up to 80,000 words</p>"
        "<p><b>POST /generate-file</b> — Upload .txt file: form fields: file + key</p>"
        "</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "voice": "OSOBA_KEHINDE_CLONE_ENHANCED"}

@app.post("/generate")
async def generate(request: Request):
    """Generate from JSON text — unlimited length via chunking."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    if SECRET_KEY and body.get("key", "") != SECRET_KEY:
        raise HTTPException(403, "Invalid key")

    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "No text provided")

    return await _process_text(text)

@app.post("/generate-file")
async def generate_file(
    file: UploadFile = File(...),
    key: str = Form(default="")
):
    """Generate from uploaded .txt file — supports 80,000+ words."""
    if SECRET_KEY and key != SECRET_KEY:
        raise HTTPException(403, "Invalid key")

    if not file.filename.endswith(".txt"):
        raise HTTPException(400, "Only .txt files supported")

    content = await file.read()
    try:
        text = content.decode("utf-8").strip()
    except Exception:
        raise HTTPException(400, "Could not read file — make sure it's UTF-8 encoded")

    if not text:
        raise HTTPException(400, "File is empty")

    return await _process_text(text)

async def _process_text(text: str):
    """Core generation — chunks text and concatenates audio."""
    chunks = split_into_chunks(text, max_chars=800)
    total_chunks = len(chunks)
    word_count = len(text.split())

    print(f"[OSOBA] Generating {word_count} words in {total_chunks} chunks...")

    wav_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"[OSOBA] Chunk {i+1}/{total_chunks}: {len(chunk)} chars")
        try:
            chunk_bytes = await asyncio.get_event_loop().run_in_executor(
                None, generate_chunk, chunk
            )
            wav_chunks.append(chunk_bytes)
        except Exception as e:
            raise HTTPException(500, f"Error on chunk {i+1}/{total_chunks}: {str(e)}")

    final_audio = concatenate_wav_bytes(wav_chunks)

    return JSONResponse({
        "success":    True,
        "audio":      base64.b64encode(final_audio).decode(),
        "format":     "wav",
        "voice":      "OSOBA_KEHINDE_CLONE_ENHANCED",
        "words":      word_count,
        "chunks":     total_chunks,
        "chars":      len(text),
    })
