import os
import io
import base64
import tempfile
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

app = FastAPI()

SECRET_KEY = os.environ.get("OSOBA_SECRET", "")

# Reference audio as base64 — embedded so no file upload needed
REF_AUDIO_PATH = os.path.join(os.path.dirname(__file__), "osoba_reference.wav")
REF_TEXT = "Welcome to OptiToon Creations. Today we're diving deep into the world of organized crime — the hierarchies, the rules, and the ruthless power struggles that defined some of history's most dangerous organizations. Stay with me, because this story goes deeper than you think."

print("[OSOBA] Voice Clone Proxy — loading reference audio...")
with open(REF_AUDIO_PATH, "rb") as f:
    REF_AUDIO_B64 = base64.b64encode(f.read()).decode()
print("[OSOBA] Reference audio loaded OK.")

@app.get("/", response_class=HTMLResponse)
def root():
    return (
        "<html><body style='font-family:monospace;background:#0a1628;color:#4f9fff;padding:40px'>"
        "<h2>🎙 OSOBA Voice Clone Studio</h2>"
        "<p>Status: <b>ONLINE</b></p>"
        "<p>Voice: <b>OSOBA KEHINDE CLONE</b></p>"
        "<p>POST /generate — {\"text\":\"...\",\"key\":\"...\"}</p>"
        "</body></html>"
    )

@app.get("/health")
def health():
    return {"status": "ok", "voice": "OSOBA_KEHINDE_CLONE"}

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
    if len(text) > 3000:
        raise HTTPException(400, "Max 3000 characters for voice clone")

    # Call public F5-TTS space via Gradio API
    # Using gradio_client to hit the public space
    try:
        from gradio_client import Client, handle_file
        import urllib.request

        # Save reference audio temporarily
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(base64.b64decode(REF_AUDIO_B64))
            tmp_path = tmp.name

        client = Client("mrfakename/E2-F5-TTS", hf_token=None)
        result = client.predict(
            ref_audio_input=handle_file(tmp_path),
            ref_text_input=REF_TEXT,
            gen_text_input=text,
            remove_silence=True,
            api_name="/basic_tts"
        )

        # result is a path to the generated audio file
        audio_path = result[0] if isinstance(result, (list, tuple)) else result
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        os.unlink(tmp_path)

        return JSONResponse({
            "success": True,
            "audio":   base64.b64encode(audio_bytes).decode(),
            "format":  "wav",
            "voice":   "OSOBA_KEHINDE_CLONE",
            "chars":   len(text),
        })

    except Exception as e:
        raise HTTPException(500, f"Voice clone error: {str(e)}")
