# Voice Agent with Batch Task Processing

A real-time voice assistant built with LiveKit Agents that can offload complex tasks to a batch processing API. The agent uses Claude for conversational AI and delegates time-intensive tasks (like generating business plans) to Doubleword's batch API for thorough completion.

## Architecture

```
User Voice Input
       │
       ▼
┌──────────────┐
│ ElevenLabs   │  Speech-to-Text
│    STT       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Claude     │  Real-time conversation
│    LLM       │──────────────────────────┐
└──────┬───────┘                          │
       │                                  │ Complex tasks
       ▼                                  ▼
┌──────────────┐                  ┌──────────────┐
│ ElevenLabs   │                  │  Doubleword  │
│    TTS       │                  │  Batch API   │
└──────┬───────┘                  └──────┬───────┘
       │                                  │
       ▼                                  │ Async polling
Voice Output ◄────────────────────────────┘
                    (notifies when complete)
```

## Features

- **Real-time voice conversation** using LiveKit Agents framework
- **Claude-powered responses** for natural, intelligent conversation
- **Batch task offloading** - complex tasks (business plans, detailed analysis, long documents) are automatically delegated to Doubleword's batch API
- **Background polling** - automatically notifies you when batch tasks complete
- **Task persistence** - results are saved and retrievable by job ID

## How It Works

1. For simple questions, Claude responds directly in real-time
2. For complex tasks (business plans, detailed research, long documents), Claude automatically:
   - Submits the task to Doubleword's batch API
   - Confirms submission to the user
   - Polls for completion in the background
   - Notifies the user when results are ready
3. Users can check task status or retrieve results at any time

## Prerequisites

- Python 3.9+
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
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install livekit-agents livekit-plugins-anthropic livekit-plugins-elevenlabs livekit-plugins-silero openai python-dotenv
```

4. Copy the example environment file and fill in your credentials:
```bash
cp .env.example .env
```

5. Edit `.env` with your API keys.

## Running the Agent

Start the agent in development mode:
```bash
python agent.py dev
```

The agent will connect to LiveKit and wait for participants. You can connect using:
- LiveKit's [Agents Playground](https://agents-playground.livekit.io/)
- Any LiveKit client SDK
- Your own frontend application

## Environment Variables

| Variable | Description |
|----------|-------------|
| `LIVEKIT_URL` | Your LiveKit server URL |
| `LIVEKIT_API_KEY` | LiveKit API key |
| `LIVEKIT_API_SECRET` | LiveKit API secret |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `ELEVEN_API_KEY` | ElevenLabs API key for STT/TTS |
| `DOUBLEWORD_API_KEY` | Doubleword API key for batch processing |
| `BATCH_MODEL` | Model to use for batch tasks |
| `LLM_MODEL` | Claude model for real-time conversation |

## Available Voice Commands

The agent understands natural language. Examples:

- **Simple questions**: "What's the weather like?" / "Tell me a joke"
- **Complex tasks**: "Create a business plan for a coffee shop" / "Write a detailed marketing strategy"
- **Task management**: "Check my task status" / "What's the result of my last task?"

## Project Structure

```
voice_agent/
├── src/
│   ├── __init__.py       # Package exports
│   ├── assistant.py      # VoiceAssistant class with tool definitions
│   └── batch.py          # Batch API client, polling, task persistence
├── agent.py              # Entry point
├── .env                  # Environment variables (not committed)
├── .env.example          # Template for environment variables
├── .gitignore            # Git ignore rules
└── README.md             # This file
```

## License

MIT
