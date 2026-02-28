# ElevenLabs Conversational AI Integration

This project supports **ElevenLabs Conversational AI** for real-time voice experience building. The flow uses our own LLM (clarify pipeline) while ElevenLabs handles STT, TTS, and turn-taking for lower latency and a more natural voice experience.

## Architecture

- **ElevenLabs**: STT (user speech → text), TTS (our replies → speech), real-time WebSocket
- **Our backend**: Custom LLM adapter that receives chat messages from ElevenLabs and runs the clarify pipeline (detect experiences, extract, clarify) to build experience cards

## Setup

### 1. Create an ElevenLabs Agent

1. Go to [ElevenLabs Conversational AI](https://elevenlabs.io/app/conversational-ai)
2. Create a new agent
3. Configure **Custom LLM**:
   - **Custom LLM URL**: `https://YOUR_API_DOMAIN/convai/v1/chat/completions`
   - Ensure the endpoint is publicly reachable (ElevenLabs servers will POST to it)
4. Save the **Agent ID**

### 2. Environment Variables

```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_AGENT_ID=your_agent_id
ELEVENLABS_CALLBACK_BASE_URL=https://your-api-domain.com
```

- `ELEVENLABS_CALLBACK_BASE_URL`: Public base URL of your API (e.g. `https://conxa-api.onrender.com`). ElevenLabs will call `{base}/convai/v1/chat/completions`.

### 3. Conversation Identification

ElevenLabs passes the `conversation_id` when calling our custom LLM. We use it to look up the user session (created when the frontend fetches the signed URL). Supported headers:

- `X-Conversation-Id`
- `X-ElevenLabs-Conversation-Id`

## API Endpoints

### `POST /convai/signed-url`

Authenticated. Returns a signed WebSocket URL for the ElevenLabs client.

**Response:**
```json
{
  "signed_url": "wss://api.elevenlabs.io/v1/convai/...",
  "conversation_id": "..."
}
```

### `POST /convai/v1/chat/completions`

OpenAI-compatible. Called by ElevenLabs with conversation messages. We run the clarify pipeline and stream the assistant reply.

## Frontend

The builder page offers two modes:

- **Voice** (default): Uses ElevenLabs real-time voice. Click "Start voice" to connect.
- **Type**: Traditional chat (type to add experiences)

When the voice session ends, card families are refetched so new cards appear on the cards page.
