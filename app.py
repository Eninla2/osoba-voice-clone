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

SECRET_KEY     = os.environ.get("OSOBA_SECRET", "")
REF_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "osoba_reference.wav")
REF_TEXT       = "Welcome to OptiToon Creations. Today we're diving deep into the world of organized crime — the hierarchies, the rules, and the ruthless power struggles that defined some of history's most dangerous organizations. Stay with me, because this story goes deeper than you think."

print("[OSOBA] Loading reference audio...")
with open(REF_AUDIO_PATH, "rb") as f:
    REF_AUDIO_B64 = base64.b64encode(f.read()).decode()
print("[OSOBA] Voice Clone Proxy READY.")

# Public F5-TTS spaces to try in order
F5_SPACES = [
    ("mrfakename/E2-F5-TTS",     "/basic_tts"),
    ("mrfakename/E2-F5-TTS",     "/infer"),
    ("ylacombe/f5-tts",          "/basic_tts"),
    ("SWivid/F5-TTS",            "/basic_tts"),
]

def split_into_chunks(text: str, max_chars: int = 800) -> list:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 <= max_chars:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            current = sentence if len(sentence) <= max_chars else sentence[:max_chars]
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]

def generate_chunk(text_chunk: str) -> bytes:
    from gradio_client import Client, handle_file

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(base64.b64decode(REF_AUDIO_B64))
        tmp_path = tmp.name

    last_error = None
    for space_id, api_name in F5_SPACES:
        try:
            print(f"[OSOBA] Trying {space_id} → {api_name}")
            client = Client(space_id)
            result = client.predict(
                ref_audio_input  = handle_file(tmp_path),
                ref_text_input   = REF_TEXT,
                gen_text_input   = text_chunk,
                remove_silence   = True,
                api_name         = api_name,
            )
            audio_path = result[0] if isinstance(result, (list, tuple)) else result
            with open(audio_path, "rb") as f:
                data = f.read()
            os.unlink(tmp_path)
            print(f"[OSOBA] Success with {space_id}")
            return data
        except Exception as e:
            print(f"[OSOBA] {space_id} failed: {e}")
            last_error = e
            continue

    os.unlink(tmp_path)
    raise RuntimeError(f"All F5-TTS spaces failed. Last error: {last_error}")

def concatenate_wav_bytes(wav_chunks: list) -> bytes:
    arrays, sr = [], 24000
    for chunk_bytes in wav_chunks:
        buf = io.BytesIO(chunk_bytes)
        try:
            data, sr = sf.read(buf)
            arrays.append(data)
        except Exception:
            continue
    if not arrays:
        raise ValueError("No valid audio chunks to concatenate")
    full = np.concatenate(arrays)
    out  = io.BytesIO()
    sf.write(out, full, sr, format="WAV")
    out.seek(0)
    return out.read()

@app.get("/", response_class=HTMLResponse)
def root():
    return (
        "<html><body style='font-family:monospace;background:#0a1628;color:#4f9fff;padding:40px'>"
        "<h2>OSOBA Voice Clone Studio</h2>"
        "<p>Status: <b>ONLINE</b></p>"
        "<p>Voice: <b>OSOBA KEHINDE CLONE (Enhanced)</b></p>"
        "<p>POST /generate — JSON {text, key}</p>"
        "<p>POST /generate-file — multipart {file .txt, key}</p>"
        "</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "voice": "OSOBA_KEHINDE_CLONE_ENHANCED"}

@app.post("/generate")
async def generate(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")
    if SECRET_KEY and body.get("key", "") != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "No text provided")
    if len(text) > 500000:
        raise HTTPException(400, "Text too long")
    return await _process_text(text)

@app.post("/generate-file")
async def generate_file(file: UploadFile = File(...), key: str = Form(default="")):
    if SECRET_KEY and key != SECRET_KEY:
        raise HTTPException(403, "Invalid key")
    if not file.filename.endswith(".txt"):
        raise HTTPException(400, "Only .txt files supported")
    content = await file.read()
    try:
        text = content.decode("utf-8").strip()
    except Exception:
        raise HTTPException(400, "Could not read file — use UTF-8 encoding")
    if not text:
        raise HTTPException(400, "File is empty")
    return await _process_text(text)

async def _process_text(text: str):
    chunks      = split_into_chunks(text, max_chars=800)
    total       = len(chunks)
    word_count  = len(text.split())
    print(f"[OSOBA] {word_count} words → {total} chunks")

    wav_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"[OSOBA] Chunk {i+1}/{total}")
        try:
            chunk_bytes = await asyncio.get_event_loop().run_in_executor(
                None, generate_chunk, chunk
            )
            wav_chunks.append(chunk_bytes)
        except Exception as e:
            raise HTTPException(500, f"Error on chunk {i+1}/{total}: {str(e)}")

    final = concatenate_wav_bytes(wav_chunks)
    return JSONResponse({
        "success": True,
        "audio":   base64.b64encode(final).decode(),
        "format":  "wav",
        "voice":   "OSOBA_KEHINDE_CLONE_ENHANCED",
        "words":   word_count,
        "chunks":  total,
        "chars":   len(text),
    })
