# Voice Agent with Batch Task Processing

A real-time voice assistant built with LiveKit Agents that can offload complex tasks to a batch processing API. The agent uses Claude for conversational AI and delegates time-intensive tasks (like generating business plans) to Doubleword's batch API for thorough completion.

## Architecture

```
User Voice Input
       |
       v
+--============--+
| ElevenLabs STT |  Speech-to-Text
+-------+--------+
        |
        v
+--============--+
|   Claude LLM   |  Real-time conversation
+-------+--------+---------------------+
        |                               |
        v                               v  Complex tasks
+--============--+             +--============--+
| ElevenLabs TTS |             | Doubleword     |
+-------+--------+             | Batch API      |
        |                      +-------+--------+
        v                              |
  Voice Output  <----- TTS notify -----+
                   (interrupts current speech
                    when task completes)
```

## Features

- **Real-time voice conversation** using LiveKit Agents framework
- **Claude-powered responses** for natural, intelligent conversation
- **Batch task offloading** - complex tasks (business plans, detailed analysis, long documents) are automatically delegated to Doubleword's batch API
- **Mid-conversation notifications** - the agent interrupts itself to notify you when a batch task completes, then offers to read the results
- **Deduplication** - prevents accidental duplicate task submissions within a 60-second window
- **Task persistence** - results are saved to `tasks_results.json` and retrievable by job ID

## How Async Batch Processing Works

The agent handles complex tasks asynchronously so the user can keep chatting while work happens in the background:

1. **Submission** - When the user requests a complex task (e.g., "Create a business plan for a coffee shop"), the LLM recognizes it requires detailed output and calls the `submit_batch_task` tool. This uploads a JSONL request to the Doubleword batch API and returns immediately.

2. **Background polling** - An `asyncio` task starts polling the batch API every 10 seconds using an `AsyncOpenAI` client (non-blocking). The user can continue a normal conversation during this time.

3. **Mid-conversation notification** - When the batch job completes:
   - The poller calls `session.interrupt(force=True)` to stop whatever the agent is currently saying
   - Then calls `session.say(...)` to directly speak a notification via TTS (bypasses the LLM for reliability)
   - The user hears something like: *"Your task 'business plan for coffee shop' is ready. Would you like me to read the results?"*

4. **Result retrieval** - When the user asks for results, the LLM calls `get_task_result` which reads from the persisted `tasks_results.json` file and speaks the content.

Key implementation details:
- The `AsyncOpenAI` client is used for polling to avoid blocking the event loop
- Background tasks are stored in a `_background_tasks` set to prevent garbage collection on Python 3.12+
- A timestamp-based deduplication guard prevents the same task from being submitted twice within 60 seconds (this can happen when LiveKit interrupts speech mid-tool-call and the LLM retries)

## Prerequisites

- Python 3.10+ (required by `livekit-agents` for `TypeAlias` support)
- LiveKit Cloud account (or self-hosted LiveKit server)
- Anthropic API key
- ElevenLabs API key
- Doubleword API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/voice-agent.git
cd voice-agent
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
```

5. Edit `.env` with your API keys (see [Environment Variables](#environment-variables) below).

## Running the Agent

Start the agent in development mode (auto-reloads on file changes):
```bash
python agent.py dev
```

For production:
```bash
python agent.py start
```

## Testing with LiveKit

Once the agent is running, you need a LiveKit room to connect to it. The easiest way:

1. Go to [LiveKit Agents Playground](https://agents-playground.livekit.io/)
2. Enter your LiveKit project URL (the `LIVEKIT_URL` from your `.env`)
3. Click **Connect** - the playground creates a room and the agent automatically joins
4. Use your microphone to talk to the agent

The agent logs will show the connection in your terminal:
```
INFO  livekit.agents  received job request  {"room": "playground-xxxx", ...}
```

Alternatively, you can connect using any [LiveKit client SDK](https://docs.livekit.io/client-sdk-js/) or build your own frontend.

**Dev mode tips:**
- The agent runs each job in a separate subprocess and watches for file changes
- Edit any `.py` file and the agent restarts automatically
- Logs include `[POLL]` prefixed lines showing batch job polling activity

## Environment Variables

| Variable | Description |
|----------|-------------|
| `LIVEKIT_URL` | Your LiveKit server URL (e.g., `wss://your-project.livekit.cloud`) |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `ELEVEN_API_KEY` | ElevenLabs API key for STT/TTS |
| `DOUBLEWORD_API_KEY` | Doubleword API key for batch processing |
| `BATCH_MODEL` | Model to use for batch tasks (default: `Qwen/Qwen3-VL-235B-A22B-Instruct-FP8`) |
| `LLM_MODEL` | Claude model for real-time conversation (e.g., `claude-sonnet-4-20250514`) |

## Available Voice Commands

The agent understands natural language. Examples:

- **Simple questions**: "What's the weather like?" / "Tell me a joke"
- **Complex tasks**: "Create a business plan for a coffee shop" / "Write a detailed marketing strategy"
- **Task management**: "Check my task status" / "What's the result of my last task?"

## Project Structure

```
voice_agent/
├── src/
│   ├── __init__.py        # Package exports
│   ├── assistant.py       # VoiceAssistant class with tool definitions
│   └── batch.py           # Batch API client, polling, task persistence
├── agent.py               # Entry point - session setup and LiveKit worker
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not committed)
├── .env.example           # Template for environment variables
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

## License

MIT
