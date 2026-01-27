import os
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, RoomInputOptions
from livekit.plugins import anthropic, elevenlabs, silero

from src import VoiceAssistant

load_dotenv()

session_holder: list = [None]


async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=elevenlabs.STT(),
        llm=anthropic.LLM(model=os.getenv("LLM_MODEL")),
        tts=elevenlabs.TTS(),
        vad=silero.VAD.load(),
    )

    session_holder[0] = session

    await session.start(
        agent=VoiceAssistant(session_ref=session_holder),
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    await session.generate_reply(
        instructions="Greet the user and ask how you can help."
    )


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
