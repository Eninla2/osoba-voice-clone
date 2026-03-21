/**
 * OSOBA VOICE STUDIO — Edge TTS Server v4.1
 * OptiToon Creations
 *
 * 100% FREE — Uses Microsoft Edge TTS (no API key, no billing, no limits)
 * Same API contract — WordPress plugin needs zero changes.
 *
 * ENV VARS (set in Render dashboard):
 *   OVS_SECRET  — Secret key matching your WP plugin settings
 *   PORT        — Set automatically by Render
 */

'use strict';

const express              = require('express');
const { MsEdgeTTS, OUTPUT_FORMAT } = require('msedge-tts');
const rateLimit            = require('express-rate-limit');
const helmet               = require('helmet');
const cors                 = require('cors');

const app  = express();
const PORT = process.env.PORT || 3000;

const OVS_SECRET = process.env.OVS_SECRET || '';
const VERSION    = '4.1.0';

// ── VOICES ────────────────────────────────────────────────────────────────
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
  'en-US-MichelleNeural':    'US Female — Friendly, Clear',
  'en-US-MonicaNeural':      'US Female — Professional, Smooth',
  'en-US-SaraNeural':        'US Female — Bright, Energetic',

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
  'en-GB-LibbyNeural':       'British Female — Gentle, Clear',
  'en-GB-MaisieNeural':      'British Female — Young, Natural',

  // AUSTRALIAN MALE
  'en-AU-WilliamNeural':     'Australian Male — Warm, Confident',
  'en-AU-DuncanNeural':      'Australian Male — Casual, Natural',
  'en-AU-KenNeural':         'Australian Male — Steady, Calm',
  'en-AU-NeilNeural':        'Australian Male — Professional',
  'en-AU-TimNeural':         'Australian Male — Friendly, Clear',

  // AUSTRALIAN FEMALE
  'en-AU-NatashaNeural':     'Australian Female — Clear, Bright',
  'en-AU-AnnetteNeural':     'Australian Female — Warm, Natural',
  'en-AU-CarlyNeural':       'Australian Female — Lively, Energetic',
  'en-AU-ElsieNeural':       'Australian Female — Gentle, Soft',
  'en-AU-FreyaNeural':       'Australian Female — Confident, Modern',

  // NIGERIAN / AFRICAN
  'en-NG-AbeoNeural':        'Nigerian Male — Authentic, Natural',
  'en-NG-EzinneNeural':      'Nigerian Female — Warm, Authentic',
  'en-GH-KwameNeural':       'Ghanaian Male — Deep, Rich',
  'en-GH-AkosuaNeural':      'Ghanaian Female — Warm, Clear',
  'en-KE-AsiliaNeural':      'Kenyan Female — Bright, Natural',
  'en-KE-ChilembaNeural':    'Kenyan Male — Strong, Clear',
  'en-TZ-ElimuNeural':       'Tanzanian Male — Calm, Clear',
  'en-TZ-ImaniNeural':       'Tanzanian Female — Gentle, Warm',
  'en-ZA-LeahNeural':        'South African Female — Clear, Professional',
  'en-ZA-LukeNeural':        'South African Male — Warm, Confident',

  // CANADIAN
  'en-CA-ClaraNeural':       'Canadian Female — Warm, Friendly',
  'en-CA-LiamNeural':        'Canadian Male — Clear, Natural',

  // IRISH
  'en-IE-ConnorNeural':      'Irish Male — Warm, Charming',
  'en-IE-EmilyNeural':       'Irish Female — Gentle, Bright',

  // SCOTTISH
  'en-GB-MiaNeural':         'Scottish Female — Clear, Natural',

  // INDIAN
  'en-IN-NeerjaNeural':      'Indian Female — Clear, Professional',
  'en-IN-PrabhatNeural':     'Indian Male — Confident, Clear',
  'en-IN-AaravNeural':       'Indian Male — Young, Natural',
  'en-IN-AnanyaNeural':      'Indian Female — Warm, Expressive',
  'en-IN-KavyaNeural':       'Indian Female — Bright, Energetic',
  'en-IN-KunalNeural':       'Indian Male — Deep, Authoritative',
  'en-IN-RehaanNeural':      'Indian Male — Casual, Modern',

  // FILIPINO
  'en-PH-JamesNeural':       'Filipino Male — Friendly, Clear',
  'en-PH-RosaNeural':        'Filipino Female — Warm, Natural',

  // SINGAPOREAN
  'en-SG-LunaNeural':        'Singaporean Female — Clear, Bright',
  'en-SG-WayneNeural':       'Singaporean Male — Professional',

  // HONG KONG
  'en-HK-SamNeural':         'Hong Kong Male — Clear, Professional',
  'en-HK-YanNeural':         'Hong Kong Female — Warm, Natural',
};

// ── SPEED MAP (SSML rate values) ──────────────────────────────────────────
const SPEED_RATE = {
  slow:   '-20%',
  normal: '+0%',
  fast:   '+20%',
};

// ── MIDDLEWARE ────────────────────────────────────────────────────────────
app.use(helmet({ crossOriginResourcePolicy: false }));
app.use(express.json({ limit: '1mb' }));

// CORS — allow everything including Chrome extensions
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  if (req.method === 'OPTIONS') return res.status(200).end();
  next();
});
app.use(cors());

// Rate limiting
const generateLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 30,
  message: { success: false, detail: 'Too many requests, please slow down.' }
});

// ── AUTH ──────────────────────────────────────────────────────────────────
function authOk(req) {
  const key = req.body?.key || req.query?.key || '';
  if (!OVS_SECRET) return true;
  return key === OVS_SECRET;
}

// ── HELPERS ───────────────────────────────────────────────────────────────
async function generateAudio(text, voice, speed) {
  const rate = SPEED_RATE[speed] || '+0%';

  const tts = new MsEdgeTTS();
  await tts.setMetadata(
    voice,
    OUTPUT_FORMAT.AUDIO_24KHZ_48KBITRATE_MONO_MP3,
    // Inject prosody rate via SSML override
    `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>
      <voice name='${voice}'>
        <prosody rate='${rate}'>${text}</prosody>
      </voice>
    </speak>`
  );

  return new Promise((resolve, reject) => {
    const chunks = [];
    const readable = tts.toStream(text);

    readable.on('data', (chunk) => chunks.push(chunk));
    readable.on('end', () => {
      if (chunks.length === 0) return reject(new Error('No audio generated'));
      resolve(Buffer.concat(chunks).toString('base64'));
    });
    readable.on('error', reject);
  });
}

// ── ROUTES ────────────────────────────────────────────────────────────────

// GET /health
app.get('/health', (req, res) => {
  res.json({
    success:      true,
    version:      VERSION,
    voice_count:  Object.keys(VOICES).length,
    engine:       'Microsoft Edge TTS (100% Free)',
    status:       'ready',
  });
});

// GET /ping — UptimeRobot keep-alive
app.get('/ping', (req, res) => {
  res.json({ pong: true, time: new Date().toISOString() });
});

// GET /voices
app.get('/voices', (req, res) => {
  res.json({ success: true, voices: VOICES });
});

// POST /generate — main voiceover generation
app.post('/generate', generateLimiter, async (req, res) => {
  if (!authOk(req)) {
    return res.status(403).json({ success: false, detail: 'Invalid secret key.' });
  }

  const { text = '', voice = 'en-GB-RyanNeural', speed = 'normal' } = req.body;

  if (!text.trim()) {
    return res.status(400).json({ success: false, detail: 'No text provided.' });
  }
  if (text.length > 50000) {
    return res.status(400).json({ success: false, detail: 'Text too long (max 50,000 chars).' });
  }
  if (!VOICES[voice]) {
    return res.status(400).json({ success: false, detail: `Unknown voice: ${voice}` });
  }

  const start = Date.now();
  try {
    const b64Audio = await generateAudio(text, voice, speed);
    const ms = Date.now() - start;
    console.log(`[generate] voice=${voice} speed=${speed} chars=${text.length} time=${ms}ms`);
    res.json({ success: true, audio: b64Audio, format: 'mp3', chars: text.length, ms });
  } catch (err) {
    console.error(`[generate] ERROR:`, err.message);
    res.status(500).json({ success: false, detail: err.message });
  }
});

// POST /preview — short voice sample
app.post('/preview', async (req, res) => {
  if (!authOk(req)) {
    return res.status(403).json({ success: false, detail: 'Invalid secret key.' });
  }

  const { voice = 'en-GB-RyanNeural' } = req.body;
  const previewText = 'Hello! This is a preview of the selected voice from OptiToon Creations Voice Studio.';

  try {
    const b64Audio = await generateAudio(previewText, voice, 'normal');
    res.json({ success: true, audio: b64Audio, format: 'mp3' });
  } catch (err) {
    res.status(500).json({ success: false, detail: err.message });
  }
});

// ── START ─────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\n🎙 Osoba Voice Studio — Edge TTS Server v${VERSION}`);
  console.log(`   Port:    ${PORT}`);
  console.log(`   Engine:  Microsoft Edge TTS (FREE — no API key needed)`);
  console.log(`   Voices:  ${Object.keys(VOICES).length}`);
  console.log(`   Secret:  ${OVS_SECRET ? '✓ set' : '⚠ not set (open access)'}`);
  console.log(`   Status:  Ready\n`);
});
