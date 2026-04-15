require('dotenv').config();
const express = require('express');
const Anthropic = require('@anthropic-ai/sdk');
const twilio = require('twilio');
const { twiml: { VoiceResponse } } = twilio;
const { v4: uuidv4 } = require('uuid');
const fs = require('fs');
const path = require('path');
const rateLimit = require('express-rate-limit');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ── Rate limiting — prevent abuse ──
const twilioLimiter = rateLimit({
  windowMs: 1 * 60 * 1000,
  max: 60,
  message: 'Too many requests',
  standardHeaders: true,
  legacyHeaders: false,
});
app.use('/twilio', twilioLimiter);

// ── Twilio request validation middleware ──
function validateTwilioRequest(req, res, next) {
  const authToken = process.env.TWILIO_AUTH_TOKEN;
  if (!authToken) {
    console.warn('⚠️  TWILIO_AUTH_TOKEN not set — skipping validation');
    return next();
  }
  const twilioSignature = req.headers['x-twilio-signature'] || '';
  const url = `${process.env.NGROK_URL}${req.originalUrl}`;
  const isValid = twilio.validateRequest(authToken, twilioSignature, url, req.body || {});
  if (isValid) {
    return next();
  }
  console.warn('🚫 Invalid Twilio signature — request rejected');
  res.status(403).send('Forbidden');
}
app.use('/twilio', validateTwilioRequest);

// ── Audio files directory ──
const AUDIO_DIR = path.join(__dirname, 'audio');
if (!fs.existsSync(AUDIO_DIR)) fs.mkdirSync(AUDIO_DIR);

// Serve audio files statically
app.use('/audio', express.static(AUDIO_DIR));

// ── Claude AI client ──
const claude = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// ── ElevenLabs TTS — convert text to audio using your cloned voice ──
async function textToSpeech(text) {
  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${process.env.ELEVENLABS_VOICE_ID}`,
    {
      method: 'POST',
      headers: {
        'xi-api-key': process.env.ELEVENLABS_API_KEY,
        'Content-Type': 'application/json',
        'Accept': 'audio/mpeg',
      },
      body: JSON.stringify({
        text,
        model_id: 'eleven_monolingual_v1',
        voice_settings: {
          stability: 0.4,
          similarity_boost: 0.78,
          style: 0.03,
          use_speaker_boost: true,
        },
      }),
    }
  );

  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`ElevenLabs error ${response.status}: ${errText}`);
  }

  // Save audio to a temp file
  const filename = `${uuidv4()}.mp3`;
  const filepath = path.join(AUDIO_DIR, filename);
  const buffer = Buffer.from(await response.arrayBuffer());
  fs.writeFileSync(filepath, buffer);

  // Clean up old audio files (older than 5 min)
  cleanOldAudio();

  return filename;
}

// ── Helper: speak text via ElevenLabs, fall back to Twilio Say ──
async function speak(response, text) {
  try {
    const filename = await textToSpeech(text);
    const audioUrl = `${process.env.NGROK_URL}/audio/${filename}`;
    response.play(audioUrl);
    console.log(`🔊 Playing cloned voice: ${audioUrl}`);
  } catch (err) {
    console.error('ElevenLabs error, falling back to Twilio Say:', err.message);
    response.say({ voice: 'alice' }, text);
  }
}

// ── Clean audio files older than 5 minutes ──
function cleanOldAudio() {
  const cutoff = Date.now() - 5 * 60 * 1000;
  for (const file of fs.readdirSync(AUDIO_DIR)) {
    const fp = path.join(AUDIO_DIR, file);
    try {
      if (fs.statSync(fp).mtimeMs < cutoff) fs.unlinkSync(fp);
    } catch (_) {}
  }
}

// ── In-memory conversation store (keyed by caller phone number) ──
// Each entry: { messages: [], lastActivity: Date.now() }
const conversations = new Map();

// ── Business hours check ──
function isDuringBusinessHours() {
  const now = new Date();
  const formatter = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    hour12: false,
    timeZone: process.env.BUSINESS_TIMEZONE || 'America/New_York',
  });
  const hour = parseInt(formatter.format(now), 10);
  const start = parseInt(process.env.BUSINESS_HOURS_START || '9', 10);
  const end = parseInt(process.env.BUSINESS_HOURS_END || '17', 10);
  const day = new Intl.DateTimeFormat('en-US', {
    weekday: 'short',
    timeZone: process.env.BUSINESS_TIMEZONE || 'America/New_York',
  }).format(now);
  if (day === 'Sat' || day === 'Sun') return false;
  return hour >= start && hour < end;
}

// ── Claude system prompt — the "brain" of the hybrid bot ──
const SYSTEM_PROMPT = `You are the Quote2ContractPro hybrid voice bot. You work for a professional quoting and contracting company.

PERSONALITY:
- Warm, professional, confident, helpful
- Speak naturally — short sentences, conversational tone
- Never say "as an AI" or "as a language model"

YOUR JOB:
1. Greet callers warmly
2. Determine their intent from these categories:
   - GET_QUOTE: They want a quote for a service
   - CHECK_STATUS: They want to check on an existing quote or contract
   - SPEAK_TO_HUMAN: They want to talk to a real person
   - GENERAL_QUESTION: They have a general question
   - COMPLAINT: They have a complaint or issue
   - UNKNOWN: You can't determine their intent
3. For GET_QUOTE: Collect these details conversationally (one or two at a time):
   - Name
   - Type of service needed (e.g. gutters, roofing, painting, fascia boards, etc.)
   - Property address or suburb
   - Brief description of the project
   - Preferred timeline
   - Contact phone number or email
4. For CHECK_STATUS: Ask for their name and quote/contract reference number
5. For SPEAK_TO_HUMAN: Acknowledge and let them know you'll transfer them
6. For COMPLAINT: Listen empathetically, capture details, offer to transfer
7. For GENERAL_QUESTION: Answer if you can, otherwise offer to transfer

RULES:
- Keep responses under 2-3 sentences — this is a phone call, not a chat
- Ask only 1-2 questions at a time
- If the caller seems frustrated, offer to transfer to a human immediately
- Always confirm details back to the caller before ending
- When you have collected all needed info for a quote, summarize it back and say goodbye

AFTER-HOURS BEHAVIOR:
If told it's after hours, let the caller know:
- Office hours are Monday–Friday 9AM–5PM Eastern
- Offer to take a message (name + number + brief description)
- Promise a callback next business day

OUTPUT FORMAT:
Respond with ONLY the words you would say on the phone. No markdown, no labels, no stage directions.`;

// ── Ask Claude for a response ──
async function askClaude(callerNumber, userMessage) {
  // Get or create conversation history for this caller
  if (!conversations.has(callerNumber)) {
    conversations.set(callerNumber, { messages: [], lastActivity: Date.now() });
  }
  const conv = conversations.get(callerNumber);
  conv.lastActivity = Date.now();
  const history = conv.messages;

  // Add context about business hours to the first message
  let enrichedMessage = userMessage;
  if (history.length === 0) {
    const hoursStatus = isDuringBusinessHours() ? 'during business hours' : 'after business hours';
    enrichedMessage = `[System: It is currently ${hoursStatus}.]\n\nCaller says: ${userMessage}`;
  }

  history.push({ role: 'user', content: enrichedMessage });

  // Keep conversation history manageable (last 20 turns)
  const trimmedHistory = history.slice(-20);

  const response = await claude.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 300,
    system: SYSTEM_PROMPT,
    messages: trimmedHistory,
  });

  const assistantMessage = response.content[0].text;
  history.push({ role: 'assistant', content: assistantMessage });

  return assistantMessage;
}

// ── Extract lead details from conversation using Claude ──
async function extractLeadFromConversation(callerNumber) {
  const conv = conversations.get(callerNumber);
  if (!conv || conv.messages.length < 2) return null;
  const history = conv.messages;

  const extractionPrompt = [
    ...history,
    {
      role: 'user',
      content: `[System instruction — do NOT say this aloud]
Based on the conversation above, extract any lead/quote details collected.
Return ONLY valid JSON in this exact format (no other text):
{
  "name": "caller name or null",
  "phone": "phone number or null",
  "email": "email or null",
  "address": "property address/suburb or null",
  "service": "service type or null",
  "description": "project description or null",
  "timeline": "preferred timeline or null"
}
If a field was not mentioned, use null.`
    }
  ];

  try {
    const response = await claude.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 300,
      system: 'You are a data extraction assistant. Return ONLY valid JSON, nothing else.',
      messages: extractionPrompt,
    });

    const jsonText = response.content[0].text.trim();
    return JSON.parse(jsonText);
  } catch (err) {
    console.error('Lead extraction error:', err.message);
    return null;
  }
}

// ── Submit lead to Legacy CRM (SQLite) ──
async function submitToLegacyCRM(lead, callerNumber) {
  const crmUrl = process.env.CRM_API_URL;
  if (!crmUrl) {
    console.log('ℹ️  CRM_API_URL not configured — skipping legacy CRM');
    return false;
  }

  try {
    const quotePayload = {
      quote: {
        customer: {
          name: lead.name || 'Voice Bot Lead',
          phone: lead.phone || callerNumber || '',
          email: lead.email || null,
        },
        address: lead.address || 'TBD',
        total: 0,
        services: {},
      },
    };

    if (lead.service) {
      const serviceKey = lead.service.toLowerCase().replace(/\s+/g, '_');
      quotePayload.quote.services[serviceKey] = {
        checked: true,
        measure: 1,
        unit: 'job',
        price: 0,
      };
    }

    console.log('📤 Submitting lead to Legacy CRM:', crmUrl);

    const response = await fetch(`${crmUrl}/api/save-quote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(quotePayload),
    });

    const result = await response.json();

    if (result.success) {
      console.log(`✅ Legacy CRM — Quote ID: ${result.quoteId}`);
      return true;
    } else {
      console.error('Legacy CRM save failed:', result.message);
      return false;
    }
  } catch (err) {
    console.error('Legacy CRM submission error:', err.message);
    return false;
  }
}

// ── Submit lead to Pro Platform (PostgreSQL) ──
async function submitToProPlatform(lead, callerNumber) {
  const proUrl = process.env.PRO_PLATFORM_URL;
  const apiKey = process.env.VOICE_BOT_API_KEY;
  if (!proUrl || !apiKey) {
    console.log('ℹ️  PRO_PLATFORM_URL or VOICE_BOT_API_KEY not configured — skipping Pro Platform');
    return false;
  }

  try {
    const payload = {
      name: lead.name || null,
      phone: lead.phone || callerNumber || null,
      email: lead.email || null,
      address: lead.address || null,
      service: lead.service || null,
      description: lead.description || null,
      timeline: lead.timeline || null,
      callerNumber: callerNumber || null,
    };

    console.log('📤 Submitting lead to Pro Platform:', proUrl);

    const response = await fetch(`${proUrl}/api/voice-bot`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-service-api-key': apiKey,
      },
      body: JSON.stringify(payload),
    });

    const result = await response.json();

    if (result.success) {
      console.log(`✅ Pro Platform — Lead: ${result.leadId}, Quote: ${result.quoteNumber}`);
      return true;
    } else {
      console.error('Pro Platform save failed:', result.error);
      return false;
    }
  } catch (err) {
    console.error('Pro Platform submission error:', err.message);
    return false;
  }
}

// ── Submit lead to BOTH CRMs ──
async function submitLeadToCRM(lead, callerNumber) {
  const results = await Promise.allSettled([
    submitToLegacyCRM(lead, callerNumber),
    submitToProPlatform(lead, callerNumber),
  ]);

  const legacyOk = results[0].status === 'fulfilled' && results[0].value;
  const proOk = results[1].status === 'fulfilled' && results[1].value;

  if (legacyOk || proOk) {
    console.log(`✅ Lead submitted — Legacy: ${legacyOk ? 'yes' : 'no'}, Pro: ${proOk ? 'yes' : 'no'}`);
    return true;
  }
  console.error('❌ Lead submission failed on both CRMs');
  return false;
}

// ── Health check ──
app.get('/', (req, res) => {
  res.send('Quote2ContractPro Voice Bot – Server is running (Claude AI active)');
});

// ── Twilio voice webhook — incoming call ──
app.post('/twilio/webhook', async (req, res) => {
  const callerNumber = req.body.From || 'unknown';
  console.log('📞 Incoming call from:', callerNumber);

  // Reset conversation for new call
  conversations.delete(callerNumber);

  const response = new VoiceResponse();

  try {
    // Get Claude's greeting
    const greeting = await askClaude(callerNumber, 'The caller just dialed in. Greet them.');

    // Speak greeting with cloned voice
    await speak(response, greeting);

    // Gather caller's speech
    const gather = response.gather({
      input: 'speech',
      timeout: 5,
      speechTimeout: 'auto',
      action: '/twilio/handle-input',
      method: 'POST',
    });

    // If no input, prompt again
    await speak(response, "I didn't catch that. Could you please repeat?");
    response.redirect('/twilio/webhook');
  } catch (err) {
    console.error('Claude error on greeting:', err.message);
    response.say(
      { voice: 'alice' },
      'Welcome to Quote 2 Contract Pro. How can we help you today?'
    );
    const gather = response.gather({
      input: 'speech',
      timeout: 5,
      speechTimeout: 'auto',
      action: '/twilio/handle-input',
      method: 'POST',
    });
    gather.say({ voice: 'alice' }, 'Please describe what you need.');
    response.redirect('/twilio/webhook');
  }

  res.type('text/xml');
  res.send(response.toString());
});

// ── Handle caller speech — send to Claude, respond ──
app.post('/twilio/handle-input', async (req, res) => {
  const callerNumber = req.body.From || 'unknown';
  const speechResult = req.body.SpeechResult || '';
  const confidence = req.body.Confidence || 'N/A';
  console.log(`🗣️  Caller [${callerNumber}] said: "${speechResult}" (confidence: ${confidence})`);

  const response = new VoiceResponse();

  try {
    const aiReply = await askClaude(callerNumber, speechResult);
    console.log(`🤖 Claude replied: "${aiReply}"`);

    // Detect if Claude's response signals end of conversation
    const lowerReply = aiReply.toLowerCase();
    const isGoodbye = lowerReply.includes('goodbye') ||
                      lowerReply.includes('good bye') ||
                      lowerReply.includes('have a great day') ||
                      lowerReply.includes('talk to you soon');

    const isTransfer = lowerReply.includes('transfer') ||
                       lowerReply.includes('connect you') ||
                       lowerReply.includes('putting you through');

    if (isTransfer) {
      // Say Claude's message, then transfer to a human
      await speak(response, aiReply);
      await speak(response, 'Please hold while I connect you.');
      // Dial real business number for human handoff
      const transferTo = process.env.TRANSFER_TO_NUMBER || process.env.TWILIO_PHONE_NUMBER;
      response.dial(transferTo);
    } else if (isGoodbye) {
      // Say goodbye and hang up
      await speak(response, aiReply);
      response.hangup();

      // Extract lead and submit to CRM
      const lead = await extractLeadFromConversation(callerNumber);
      if (lead && (lead.name || lead.phone || lead.service)) {
        await submitLeadToCRM(lead, callerNumber);
      } else {
        console.log('ℹ️  No lead data to submit for:', callerNumber);
      }

      // Clean up conversation
      conversations.delete(callerNumber);
    } else {
      // Continue the conversation — say Claude's response, gather more input
      await speak(response, aiReply);

      const gather = response.gather({
        input: 'speech',
        timeout: 6,
        speechTimeout: 'auto',
        action: '/twilio/handle-input',
        method: 'POST',
      });

      // If no input after timeout
      await speak(response, "Are you still there? I didn't hear anything.");
      response.redirect('/twilio/handle-input');
    }
  } catch (err) {
    console.error('Claude error:', err.message);
    response.say(
      { voice: 'alice' },
      "I'm sorry, I'm having trouble right now. Let me connect you to someone who can help."
    );
    const transferTo = process.env.TRANSFER_TO_NUMBER || process.env.TWILIO_PHONE_NUMBER;
    response.dial(transferTo);
  }

  res.type('text/xml');
  res.send(response.toString());
});

// ── Twilio status callback — track call events ──
app.post('/twilio/status-callback', (req, res) => {
  const { CallSid, CallStatus, CallDuration, From, To } = req.body;
  console.log(`📊 Call ${CallSid}: ${CallStatus} | From: ${From} → To: ${To} | Duration: ${CallDuration || 'N/A'}s`);

  // Clean up conversation on terminal call states
  if (['completed', 'busy', 'no-answer', 'canceled', 'failed'].includes(CallStatus)) {
    const callerNumber = From || 'unknown';
    if (conversations.has(callerNumber)) {
      console.log(`🧹 Cleaning up conversation for ${callerNumber} (call ${CallStatus})`);
      conversations.delete(callerNumber);
    }
  }

  res.sendStatus(204);
});

// ── Cleanup stale conversations every 10 minutes ──
setInterval(() => {
  const now = Date.now();
  const staleAfter = 30 * 60 * 1000; // 30 min inactivity
  let cleaned = 0;
  for (const [caller, conv] of conversations) {
    if (now - conv.lastActivity > staleAfter) {
      conversations.delete(caller);
      cleaned++;
    }
  }
  if (cleaned > 0) {
    console.log(`🧹 Cleaned ${cleaned} stale conversations (${conversations.size} remaining)`);
  }
}, 10 * 60 * 1000);

// ── Periodic audio cleanup every 5 minutes ──
setInterval(() => {
  cleanOldAudio();
}, 5 * 60 * 1000);

// ── Start server ──
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✅ Server listening on port ${PORT}`);
  console.log(`🤖 Claude AI brain: active`);
  console.log(`🎙️  ElevenLabs voice: ${process.env.ELEVENLABS_VOICE_ID}`);
  console.log(`📞 Twilio phone: ${process.env.TWILIO_PHONE_NUMBER}`);
  console.log(`� Transfer to: ${process.env.TRANSFER_TO_NUMBER || '(same as Twilio number)'}`);
  console.log(`🕐 Business hours: ${process.env.BUSINESS_HOURS_START || 9}–${process.env.BUSINESS_HOURS_END || 17} ${process.env.BUSINESS_TIMEZONE || 'America/New_York'}`);
  console.log(`🔐 Twilio validation: ${process.env.TWILIO_AUTH_TOKEN ? 'enabled' : 'disabled (no auth token)'}`);
});
