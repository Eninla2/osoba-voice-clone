/**
 * OSOBA VOICE STUDIO — Google Cloud TTS Server v3.0
 * OptiToon Creations
 *
 * Drop-in replacement for the Edge TTS / Azure server.
 * Same API contract — WordPress plugin needs zero changes.
 *
 * ENV VARS (set in Render dashboard):
 *   GOOGLE_API_KEY  — Your Google Cloud API key
 *   OVS_SECRET      — Secret key you set in the WP plugin settings
 *   PORT            — Set automatically by Render
 */

'use strict';

const express   = require('express');
const axios     = require('axios');
const rateLimit = require('express-rate-limit');
const helmet    = require('helmet');
const cors      = require('cors');

const app  = express();
const PORT = process.env.PORT || 3000;

/* ══════════════════════════════════════════════
   CONFIG
══════════════════════════════════════════════ */
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || '';
const OVS_SECRET     = process.env.OVS_SECRET     || '';
const VERSION        = '3.0.0';

// Multi-user key system
// Set USER_KEYS in Render as comma-separated keys, e.g: key-alice,key-bob,key-charlie
// If USER_KEYS is not set, falls back to OVS_SECRET (single key mode)
const USER_KEYS = process.env.USER_KEYS
  ? process.env.USER_KEYS.split(',').map(k => k.trim()).filter(Boolean)
  : [];

function isValidKey(key) {
  if (!key) return false;
  // Accept master key (OVS_SECRET) always
  if (OVS_SECRET && key === OVS_SECRET) return true;
  // Accept any user key
  if (USER_KEYS.length > 0) return USER_KEYS.includes(key);
  // If no keys configured at all, allow open access
  if (!OVS_SECRET && USER_KEYS.length === 0) return true;
  return false;
}

// Google Cloud TTS REST endpoint
const GOOGLE_TTS_URL = `https://texttospeech.googleapis.com/v1/text:synthesize?key=${GOOGLE_API_KEY}`;

/* ══════════════════════════════════════════════
   VOICES
   Using WaveNet voices = $4/million chars (cheapest neural tier)
   Mapped to match your existing 70-voice plugin list
══════════════════════════════════════════════ */
const VOICES = {
  // US MALE
  'en-US-GuyNeural':         'US Male — Smooth, Authoritative',
  'en-US-ChristopherNeural': 'US Male — Rich, Professional',
  'en-US-EricNeural':        'US Male — Confident, Clear',
  'en-US-RogerNeural':       'US Male — Warm, Friendly',
  'en-US-SteffanNeural':     'US Male — Deep, Powerful',
  'en-US-AndrewNeural':      'US Male — Casual, Natural',
  'en-US-BrianNeural':       'US Male — Steady, Broadcast',
  // US FEMALE
  'en-US-JennyNeural':       'US Female — Warm, Natural',
  'en-US-AriaNeural':        'US Female — Expressive, Lively',
  'en-US-EmmaNeural':        'US Female — Warm, Expressive',
  // BRITISH MALE
  'en-GB-RyanNeural':        'British Male — Deep, Cinematic',
  'en-GB-ThomasNeural':      'British Male — Clear, Documentary',
  'en-GB-AlfieNeural':       'British Male — Relaxed, Natural',
  'en-GB-ElliotNeural':      'British Male — Crisp, Educated',
  'en-GB-EthanNeural':       'British Male — Young, Engaging',
  'en-GB-NoahNeural':        'British Male — Calm, Measured',
  'en-GB-OliverNeural':      'British Male — Warm, Friendly',
  // BRITISH FEMALE
  'en-GB-SoniaNeural':       'British Female — Crisp, Elegant',
  'en-GB-LibbyNeural':       'British Female — Light, Cheerful',
  'en-GB-MaisieNeural':      'British Female — Youthful, Bright',
  'en-GB-AbbiNeural':        'British Female — Clear, Confident',
  'en-GB-BellaNeural':       'British Female — Warm, Natural',
  'en-GB-HollieNeural':      'British Female — Smooth, Professional',
  'en-GB-OliviaNeural':      'British Female — Polished, Assured',
  // AUSTRALIAN MALE
  'en-AU-WilliamNeural':     'Australian Male — Relaxed, Friendly',
  'en-AU-DarrenNeural':      'Australian Male — Direct, Clear',
  'en-AU-DuncanNeural':      'Australian Male — Steady, Natural',
  'en-AU-KenNeural':         'Australian Male — Warm, Casual',
  'en-AU-NeilNeural':        'Australian Male — Confident, Smooth',
  'en-AU-TimNeural':         'Australian Male — Laid-back, Easy',
  // AUSTRALIAN FEMALE
  'en-AU-NatashaNeural':     'Australian Female — Warm, Natural',
  'en-AU-AnnetteNeural':     'Australian Female — Bright, Friendly',
  'en-AU-CarlyNeural':       'Australian Female — Crisp, Upbeat',
  'en-AU-ElsieNeural':       'Australian Female — Soft, Gentle',
  'en-AU-FreyaNeural':       'Australian Female — Energetic, Vivid',
  'en-AU-JoanneNeural':      'Australian Female — Calm, Assured',
  'en-AU-KimNeural':         'Australian Female — Soothing, Clear',
  'en-AU-TinaNeural':        'Australian Female — Cheerful, Lively',
  // AFRICAN
  'en-NG-AbeoNeural':        'Nigerian Male 🇳🇬 — Rich, Authoritative',
  'en-NG-EzinneNeural':      'Nigerian Female 🇳🇬 — Warm, Expressive',
  'en-ZA-LukeNeural':        'South African Male 🇿🇦 — Deep, Distinct',
  'en-ZA-LeahNeural':        'South African Female 🇿🇦 — Clear, Vibrant',
  // ASIAN
  'en-IN-PrabhatNeural':     'Indian Male 🇮🇳 — Clear, Professional',
  'en-IN-NeerjaNeural':      'Indian Female 🇮🇳 — Warm, Expressive',
  'en-PH-JamesNeural':       'Filipino Male 🇵🇭 — Clear, Engaging',
  'en-PH-RosaNeural':        'Filipino Female 🇵🇭 — Warm, Expressive',
  'en-SG-WayneNeural':       'Singaporean Male 🇸🇬 — Crisp, Modern',
  'en-SG-LunaNeural':        'Singaporean Female 🇸🇬 — Bright, Clear',
  'en-HK-SamNeural':         'Hong Kong Male 🇭🇰 — Confident, Clear',
  'en-HK-YanNeural':         'Hong Kong Female 🇭🇰 — Smooth, Natural',
  // OTHER
  'en-IE-ConnorNeural':      'Irish Male 🇮🇪 — Warm, Charming',
  'en-IE-EmilyNeural':       'Irish Female 🇮🇪 — Soft, Melodic',
  'en-CA-LiamNeural':        'Canadian Male 🇨🇦 — Warm, Natural',
  'en-CA-ClaraNeural':       'Canadian Female 🇨🇦 — Clear, Friendly',
  'en-NZ-MitchellNeural':    'New Zealand Male 🇳🇿 — Friendly, Casual',
  'en-NZ-MollyNeural':       'New Zealand Female 🇳🇿 — Bright, Natural',
};

/*
 * VOICE MAP — translates your plugin's voice IDs to Google WaveNet voices.
 * Google voice format: language-code + voice name
 * We map each plugin voice to the closest Google WaveNet equivalent.
 * Male voices → WaveNet-B or WaveNet-D (deeper)
 * Female voices → WaveNet-A or WaveNet-C (brighter)
 */
const VOICE_MAP = {
  // US MALE → en-US WaveNet male voices
  'en-US-GuyNeural':         { languageCode: 'en-US', name: 'en-US-Wavenet-D' },
  'en-US-ChristopherNeural': { languageCode: 'en-US', name: 'en-US-Wavenet-B' },
  'en-US-EricNeural':        { languageCode: 'en-US', name: 'en-US-Wavenet-I' },
  'en-US-RogerNeural':       { languageCode: 'en-US', name: 'en-US-Wavenet-J' },
  'en-US-SteffanNeural':     { languageCode: 'en-US', name: 'en-US-Wavenet-D' },
  'en-US-AndrewNeural':      { languageCode: 'en-US', name: 'en-US-Wavenet-I' },
  'en-US-BrianNeural':       { languageCode: 'en-US', name: 'en-US-Wavenet-B' },
  // US FEMALE → en-US WaveNet female voices
  'en-US-JennyNeural':       { languageCode: 'en-US', name: 'en-US-Wavenet-F' },
  'en-US-AriaNeural':        { languageCode: 'en-US', name: 'en-US-Wavenet-H' },
  'en-US-EmmaNeural':        { languageCode: 'en-US', name: 'en-US-Wavenet-G' },
  // BRITISH MALE → en-GB WaveNet male
  'en-GB-RyanNeural':        { languageCode: 'en-GB', name: 'en-GB-Wavenet-B' },
  'en-GB-ThomasNeural':      { languageCode: 'en-GB', name: 'en-GB-Wavenet-D' },
  'en-GB-AlfieNeural':       { languageCode: 'en-GB', name: 'en-GB-Wavenet-B' },
  'en-GB-ElliotNeural':      { languageCode: 'en-GB', name: 'en-GB-Wavenet-D' },
  'en-GB-EthanNeural':       { languageCode: 'en-GB', name: 'en-GB-Wavenet-B' },
  'en-GB-NoahNeural':        { languageCode: 'en-GB', name: 'en-GB-Wavenet-D' },
  'en-GB-OliverNeural':      { languageCode: 'en-GB', name: 'en-GB-Wavenet-B' },
  // BRITISH FEMALE → en-GB WaveNet female
  'en-GB-SoniaNeural':       { languageCode: 'en-GB', name: 'en-GB-Wavenet-A' },
  'en-GB-LibbyNeural':       { languageCode: 'en-GB', name: 'en-GB-Wavenet-C' },
  'en-GB-MaisieNeural':      { languageCode: 'en-GB', name: 'en-GB-Wavenet-F' },
  'en-GB-AbbiNeural':        { languageCode: 'en-GB', name: 'en-GB-Wavenet-A' },
  'en-GB-BellaNeural':       { languageCode: 'en-GB', name: 'en-GB-Wavenet-C' },
  'en-GB-HollieNeural':      { languageCode: 'en-GB', name: 'en-GB-Wavenet-F' },
  'en-GB-OliviaNeural':      { languageCode: 'en-GB', name: 'en-GB-Wavenet-A' },
  // AUSTRALIAN MALE → en-AU WaveNet male
  'en-AU-WilliamNeural':     { languageCode: 'en-AU', name: 'en-AU-Wavenet-B' },
  'en-AU-DarrenNeural':      { languageCode: 'en-AU', name: 'en-AU-Wavenet-D' },
  'en-AU-DuncanNeural':      { languageCode: 'en-AU', name: 'en-AU-Wavenet-B' },
  'en-AU-KenNeural':         { languageCode: 'en-AU', name: 'en-AU-Wavenet-D' },
  'en-AU-NeilNeural':        { languageCode: 'en-AU', name: 'en-AU-Wavenet-B' },
  'en-AU-TimNeural':         { languageCode: 'en-AU', name: 'en-AU-Wavenet-D' },
  // AUSTRALIAN FEMALE → en-AU WaveNet female
  'en-AU-NatashaNeural':     { languageCode: 'en-AU', name: 'en-AU-Wavenet-A' },
  'en-AU-AnnetteNeural':     { languageCode: 'en-AU', name: 'en-AU-Wavenet-C' },
  'en-AU-CarlyNeural':       { languageCode: 'en-AU', name: 'en-AU-Wavenet-A' },
  'en-AU-ElsieNeural':       { languageCode: 'en-AU', name: 'en-AU-Wavenet-C' },
  'en-AU-FreyaNeural':       { languageCode: 'en-AU', name: 'en-AU-Wavenet-A' },
  'en-AU-JoanneNeural':      { languageCode: 'en-AU', name: 'en-AU-Wavenet-C' },
  'en-AU-KimNeural':         { languageCode: 'en-AU', name: 'en-AU-Wavenet-A' },
  'en-AU-TinaNeural':        { languageCode: 'en-AU', name: 'en-AU-Wavenet-C' },
  // AFRICAN → en-IN WaveNet (closest accent match available in Google)
  'en-NG-AbeoNeural':        { languageCode: 'en-IN', name: 'en-IN-Wavenet-B' },
  'en-NG-EzinneNeural':      { languageCode: 'en-IN', name: 'en-IN-Wavenet-A' },
  'en-ZA-LukeNeural':        { languageCode: 'en-IN', name: 'en-IN-Wavenet-C' },
  'en-ZA-LeahNeural':        { languageCode: 'en-IN', name: 'en-IN-Wavenet-D' },
  // ASIAN
  'en-IN-PrabhatNeural':     { languageCode: 'en-IN', name: 'en-IN-Wavenet-B' },
  'en-IN-NeerjaNeural':      { languageCode: 'en-IN', name: 'en-IN-Wavenet-A' },
  'en-PH-JamesNeural':       { languageCode: 'en-US', name: 'en-US-Wavenet-I' },
  'en-PH-RosaNeural':        { languageCode: 'en-US', name: 'en-US-Wavenet-H' },
  'en-SG-WayneNeural':       { languageCode: 'en-IN', name: 'en-IN-Wavenet-C' },
  'en-SG-LunaNeural':        { languageCode: 'en-IN', name: 'en-IN-Wavenet-D' },
  'en-HK-SamNeural':         { languageCode: 'en-IN', name: 'en-IN-Wavenet-B' },
  'en-HK-YanNeural':         { languageCode: 'en-IN', name: 'en-IN-Wavenet-A' },
  // OTHER
  'en-IE-ConnorNeural':      { languageCode: 'en-GB', name: 'en-GB-Wavenet-D' },
  'en-IE-EmilyNeural':       { languageCode: 'en-GB', name: 'en-GB-Wavenet-C' },
  'en-CA-LiamNeural':        { languageCode: 'en-US', name: 'en-US-Wavenet-D' },
  'en-CA-ClaraNeural':       { languageCode: 'en-US', name: 'en-US-Wavenet-F' },
  'en-NZ-MitchellNeural':    { languageCode: 'en-AU', name: 'en-AU-Wavenet-B' },
  'en-NZ-MollyNeural':       { languageCode: 'en-AU', name: 'en-AU-Wavenet-A' },
};

/* ══════════════════════════════════════════════
   SPEED MAP — plugin speed names → Google speaking rate
   1.0 = normal, <1.0 = slower, >1.0 = faster
══════════════════════════════════════════════ */
const SPEED_MAP = {
  very_slow:     0.65,
  slow:          0.82,
  normal:        1.0,
  slightly_fast: 1.18,
  fast:          1.35,
};

/* ══════════════════════════════════════════════
   CONCURRENCY LIMITER
══════════════════════════════════════════════ */
let activeRequests = 0;
const MAX_CONCURRENT = 150;

/* ══════════════════════════════════════════════
   MIDDLEWARE
══════════════════════════════════════════════ */
app.set('trust proxy', 1);
app.use(helmet({ contentSecurityPolicy: false }));
// Allow ALL origins including Chrome extensions
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-secret-key');
  if (req.method === 'OPTIONS') { return res.status(200).end(); }
  next();
});
app.use(cors());
app.use(express.json({ limit: '2mb' }));

// Global rate limit
app.use(rateLimit({
  windowMs: 60 * 1000,
  max: 300,
  standardHeaders: true,
  legacyHeaders: false,
  message: { success: false, detail: 'Too many requests. Please wait a moment.' },
}));

// Generate-specific rate limit
const generateLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 60,
  keyGenerator: (req) => req.ip + ':generate',
  message: { success: false, detail: 'Generation rate limit reached. Please wait.' },
});

/* ══════════════════════════════════════════════
   HELPERS
══════════════════════════════════════════════ */
function authOk(req) {
  const key = req.body?.key || req.query?.key || '';
  if (!OVS_SECRET) return true;
  return key === OVS_SECRET;
}

/**
 * Call Google Cloud TTS REST API.
 * Returns a Buffer of MP3 audio.
 */
async function callGoogleTTS(text, voiceId, speed) {
  if (!GOOGLE_API_KEY) throw new Error('GOOGLE_API_KEY not configured on server.');

  const googleVoice = VOICE_MAP[voiceId];
  if (!googleVoice) throw new Error(`Unknown voice: ${voiceId}`);

  const speakingRate = SPEED_MAP[speed] || 1.0;

  const requestBody = {
    input: { text },
    voice: {
      languageCode: googleVoice.languageCode,
      name:         googleVoice.name,
    },
    audioConfig: {
      audioEncoding: 'MP3',
      speakingRate,
      pitch:         0,      // natural pitch
      volumeGainDb:  0,      // natural volume
      sampleRateHertz: 24000,
    },
  };

  const url = `https://texttospeech.googleapis.com/v1/text:synthesize?key=${GOOGLE_API_KEY}`;

  const response = await axios.post(url, requestBody, {
    headers: { 'Content-Type': 'application/json' },
    timeout: 120000,
  });

  // Google returns base64 audio directly — no need to convert
  return response.data.audioContent;
}

/* ══════════════════════════════════════════════
   ROUTES
══════════════════════════════════════════════ */

// GET /health — plugin "Test Server" button
app.get('/health', (req, res) => {
  res.json({
    success:         true,
    version:         VERSION,
    voice_count:     Object.keys(VOICES).length,
    engine:          'Google Cloud WaveNet TTS',
    active_requests: activeRequests,
    status:          GOOGLE_API_KEY ? 'ready' : 'misconfigured — check GOOGLE_API_KEY',
  });
});

// GET /voices — plugin voice list (cached 1hr by plugin)
app.get('/voices', (req, res) => {
  res.json({ success: true, voices: VOICES });
});

// POST /generate — main generation (called by WP plugin)
app.post('/generate', generateLimiter, async (req, res) => {
  if (!authOk(req)) {
    return res.status(403).json({ success: false, detail: 'Invalid secret key.' });
  }

  const { text = '', voice = 'en-GB-RyanNeural', speed = 'normal' } = req.body;

  if (!text.trim()) {
    return res.status(400).json({ success: false, detail: 'No text provided.' });
  }
  if (text.length > 80000) {
    return res.status(400).json({ success: false, detail: 'Text too long (max 80,000 chars).' });
  }
  if (activeRequests >= MAX_CONCURRENT) {
    return res.status(503).json({ success: false, detail: 'Server busy. Try again shortly.' });
  }

  activeRequests++;
  const start = Date.now();

  try {
    const b64Audio = await callGoogleTTS(text, voice, speed);
    const ms = Date.now() - start;

    console.log(`[generate] voice=${voice} speed=${speed} chars=${text.length} time=${ms}ms`);

    res.json({
      success: true,
      audio:   b64Audio,   // Google already returns base64
      format:  'mp3',
      chars:   text.length,
      ms,
    });
  } catch (err) {
    const detail = parseGoogleError(err);
    console.error(`[generate] ERROR: ${detail}`);
    res.status(500).json({ success: false, detail });
  } finally {
    activeRequests--;
  }
});

// POST /preview — voice preview
app.post('/preview', async (req, res) => {
  if (!authOk(req)) {
    return res.status(403).json({ success: false, detail: 'Invalid secret key.' });
  }

  const { voice = 'en-GB-RyanNeural' } = req.body;
  const previewText = 'Hello! This is a preview of the selected voice for OptiToon Creations.';

  if (activeRequests >= MAX_CONCURRENT) {
    return res.status(503).json({ success: false, detail: 'Server busy. Try again shortly.' });
  }

  activeRequests++;
  try {
    const b64Audio = await callGoogleTTS(previewText, voice, 'normal');
    res.json({ success: true, audio: b64Audio, format: 'mp3' });
  } catch (err) {
    res.status(500).json({ success: false, detail: parseGoogleError(err) });
  } finally {
    activeRequests--;
  }
});

// GET /ping — keep-alive for UptimeRobot
app.get('/ping', (req, res) => {
  res.json({ pong: true, time: new Date().toISOString() });
});

/* ══════════════════════════════════════════════
   ERROR PARSING
══════════════════════════════════════════════ */
function parseGoogleError(err) {
  if (err.response) {
    const status = err.response.status;
    const msg    = err.response.data?.error?.message || '';
    if (status === 400) return `Bad request: ${msg || 'check voice name and text'}`;
    if (status === 401 || status === 403) return 'Google API key invalid or not authorized. Check GOOGLE_API_KEY in Render settings.';
    if (status === 429) return 'Google TTS quota exceeded. Check your Google Cloud billing.';
    if (status === 503) return 'Google TTS service unavailable. Try again shortly.';
    return `Google error ${status}: ${msg}`;
  }
  if (err.code === 'ECONNABORTED') return 'Request timed out — text may be too long.';
  return err.message || 'Unknown server error.';
}

/* ══════════════════════════════════════════════
   IMAGE GENERATION — Imagen 4 via Gemini API
   Uses the same GOOGLE_API_KEY as TTS above.
   No new credentials needed.
══════════════════════════════════════════════ */

const IMAGE_URL = `https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key=${GOOGLE_API_KEY}`;

// Health check — lets the extension confirm image generation is available
app.get('/image-health', (req, res) => {
  res.json({
    status:  'ok',
    service: 'StickFlow Image Generation',
    model:   'imagen-4.0-generate-001',
    apiKey:  GOOGLE_API_KEY ? 'set' : 'MISSING',
  });
});

// Rate limiter for image generation (1 per 2s to avoid burst billing)
const imageLimiter = rateLimit({
  windowMs: 2000,
  max: 1,
  message: { success: false, error: 'Rate limit — 1 image per 2s' },
});

// POST /generate-image
// Body: { key, prompt, aspectRatio }
// Returns: { success, image (base64), mimeType }
app.post('/generate-image', imageLimiter, async (req, res) => {
  const { key, prompt, aspectRatio } = req.body || {};

  // Auth — same OVS_SECRET used by TTS
  if (!isValidKey(key)) {
    return res.status(401).json({ success: false, error: 'Unauthorized' });
  }

  if (!prompt || typeof prompt !== 'string' || prompt.trim().length < 3) {
    return res.status(400).json({ success: false, error: 'prompt is required' });
  }

  if (!GOOGLE_API_KEY) {
    return res.status(500).json({ success: false, error: 'GOOGLE_API_KEY not configured on server' });
  }

  try {
    const response = await axios.post(IMAGE_URL, {
      instances:  [{ prompt: prompt.trim() + ', 2D stickman illustration, simple bold black outlines, flat colors, white background, minimal style, comic panel, no shading, clean linework' }],
      parameters: {
        sampleCount:     1,
        aspectRatio:     aspectRatio || '16:9',
        safetySetting:   'block_low_and_above',
        personGeneration: 'allow_adult',
      },
    }, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 60000,
    });

    const b64 = response.data?.predictions?.[0]?.bytesBase64Encoded;
    if (!b64) {
      console.error('generate-image: no image in response', JSON.stringify(response.data).slice(0, 200));
      return res.status(502).json({ success: false, error: 'No image returned from Imagen API' });
    }

    return res.json({ success: true, image: b64, mimeType: 'image/png' });

  } catch (err) {
    const status = err.response?.status;
    const msg    = err.response?.data?.error?.message || err.message;
    console.error(`generate-image error [${status}]:`, msg);
    return res.status(502).json({ success: false, error: `Imagen API ${status || 'error'}: ${msg.slice(0, 200)}` });
  }
});

/* ══════════════════════════════════════════════
   START
══════════════════════════════════════════════ */
app.listen(PORT, () => {
  console.log('');
  console.log('╔══════════════════════════════════════════════╗');
  console.log('║  OSOBA VOICE STUDIO — Google Cloud TTS       ║');
  console.log('║  OptiToon Creations  v' + VERSION + '               ║');
  console.log('╚══════════════════════════════════════════════╝');
  console.log('');
  console.log(`  Port:    ${PORT}`);
  console.log(`  Voices:  ${Object.keys(VOICES).length}`);
  console.log(`  API Key: ${GOOGLE_API_KEY ? '✓ set' : '✗ MISSING — set GOOGLE_API_KEY in env'}`);
  console.log(`  Secret:  ${OVS_SECRET ? '✓ set' : '⚠ not set (open access)'}`);
  console.log('');
});
   
