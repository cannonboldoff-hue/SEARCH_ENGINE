# Vapi AI Conversational Voice Integration

This project uses **Vapi AI** for real-time voice experience building.

## Migration from ElevenLabs

If migrating from ElevenLabs, update your `.env`:
- Replace `ELEVENLABS_API_KEY`, `ELEVENLABS_AGENT_ID`, `ELEVENLABS_CALLBACK_BASE_URL` with `VAPI_API_KEY` and `VAPI_CALLBACK_BASE_URL`. The flow uses our own LLM (clarify pipeline) while Vapi handles STT, TTS, and real-time WebRTC.

## Architecture

- **Vapi**: STT (user speech → text), TTS (our replies → speech), WebRTC transport
- **Our backend**: Custom LLM proxy; receives chat messages from Vapi and runs the clarify pipeline to build experience cards

## Setup

### 1. Create a Vapi Account

1. Sign up at [dashboard.vapi.ai](https://dashboard.vapi.ai)
2. Get your **API Key** from the dashboard

### 2. Provider Keys (Lower Cost – ElevenLabs + Deepgram)

Add your own API keys in the Vapi Dashboard so you pay ElevenLabs and Deepgram directly instead of through Vapi’s markup:

1. In [Vapi Dashboard](https://dashboard.vapi.ai) go to **Provider Keys** (or Settings → Provider Keys)
2. Add **ElevenLabs** – your ElevenLabs API key for TTS
3. Add **Deepgram** – your Deepgram API key for STT

Vapi will use these keys when the assistant uses `11labs` (voice) and `deepgram` (transcriber). You are billed by each provider plus Vapi’s platform usage.

### 3. Environment Variables

```env
VAPI_API_KEY=your_vapi_api_key
VAPI_CALLBACK_BASE_URL=https://your-api-domain.com
# Optional – defaults: 11labs, Deepgram nova-2
VAPI_VOICE_PROVIDER=11labs
VAPI_VOICE_ID=21m00Tcm4TlvDq8ikWAM
VAPI_TRANSCRIBER_PROVIDER=deepgram
VAPI_TRANSCRIBER_MODEL=nova-2
```

- `VAPI_API_KEY`: Your private Vapi API key from the dashboard
- `VAPI_CALLBACK_BASE_URL`: Public base URL of your API (e.g. `https://conxa-api.onrender.com`). Vapi calls `{base}/convai/v1/chat/completions` when using our custom LLM.
- `VAPI_VOICE_PROVIDER`, `VAPI_VOICE_ID`: Voice provider and voice ID (default: ElevenLabs)
- `VAPI_TRANSCRIBER_PROVIDER`, `VAPI_TRANSCRIBER_MODEL`: Transcriber provider and model (default: Deepgram nova-2)

### 4. Flow

1. User clicks "Start voice" in the builder
2. Frontend uses Vapi Web SDK with our API as proxy: `new Vapi(token, API_BASE + '/convai')`
3. Our `/convai/call` and `/convai/call/web` endpoints receive the request, validate JWT, and create a Vapi call with a transient assistant
4. The transient assistant uses our custom LLM URL: `{VAPI_CALLBACK_BASE_URL}/convai/v1/chat/completions?user_id={user_id}`
5. Vapi calls our chat completions endpoint with conversation messages; we run the clarify pipeline and return the reply
6. Vapi speaks the reply via TTS

## API Endpoints

### `POST /convai/call` and `POST /convai/call/web`

Proxy for Vapi web calls. Requires `Authorization: Bearer <token>`.
Creates a call with a transient assistant that uses our custom LLM.
The frontend uses the Vapi Web SDK with this URL as the proxy base.

### `POST /convai/v1/chat/completions`

OpenAI-compatible. Called by Vapi with conversation messages.
We run the clarify pipeline and stream the assistant reply.

## Troubleshooting

**If you see `503 Voice requires the callback URL to reach this server`:** You're running the API locally but `VAPI_CALLBACK_BASE_URL` points to production. Vapi's cloud calls that URL for AI responses, so it must reach the same process that created the session. For local development, expose your API via a tunnel (e.g. `ngrok http 8000`) and set `VAPI_CALLBACK_BASE_URL` to the tunnel URL (e.g. `https://abc123.ngrok.io`).

**If you see `503 Voice service unavailable`:** Check that `VAPI_API_KEY` and `VAPI_CALLBACK_BASE_URL` are set and that your API is publicly reachable.

**If you see `Missing conversation context`:** Ensure the custom LLM URL includes `user_id` as a query parameter. Our proxy adds this automatically.

**If you see `Session not found` (404) with `conversation_id=.../chat/completions`:** Vapi appends `/chat/completions` to the custom LLM URL; with some clients this can end up in the `user_id` query value. Our server strips that suffix automatically. If the issue persists, ensure `VAPI_CALLBACK_BASE_URL` is correct and the call was started via our proxy (which creates the session).

**Provider keys:** Add ElevenLabs and Deepgram keys in the Vapi Dashboard under Provider Keys to reduce cost. Without them, Vapi uses its own keys and marks up usage. Override voice/transcriber via `VAPI_VOICE_PROVIDER`, `VAPI_VOICE_ID`, `VAPI_TRANSCRIBER_PROVIDER`, `VAPI_TRANSCRIBER_MODEL` in `.env`.
