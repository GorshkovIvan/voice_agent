import os
import json
import asyncio
from pathlib import Path
from openai import AsyncOpenAI
from livekit.agents import AgentSession

# Doubleword batch API client (async to avoid blocking the event loop)
batch_client = AsyncOpenAI(
    api_key=os.getenv("DOUBLEWORD_API_KEY"),
    base_url="https://api.doubleword.ai/v1"
)

# Keep strong references to polling tasks to prevent GC (Python 3.12+)
_background_tasks: set = set()

# File to store task results
TASKS_FILE = Path(__file__).parent.parent / "tasks_results.json"


def load_tasks() -> dict:
    """Load tasks from JSON file."""
    if TASKS_FILE.exists():
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_tasks(tasks: dict):
    """Save tasks to JSON file."""
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)


async def poll_batch_job(batch_id: str, session: AgentSession, task_description: str):
    """Poll for batch job completion and notify user when done."""
    print(f"[POLL] Started polling for job {batch_id}", flush=True)
    while True:
        await asyncio.sleep(10)
        try:
            print(f"[POLL] Checking status for job {batch_id}", flush=True)
            batch_status = await batch_client.batches.retrieve(batch_id)
            print(f"[POLL] Job {batch_id} status: {batch_status.status}", flush=True)

            if batch_status.status == "completed":
                content = await batch_client.files.content(batch_status.output_file_id)
                lines = content.text.strip().split('\n')

                if lines:
                    first_result = json.loads(lines[0])
                    response_content = (
                        first_result.get("response", {})
                        .get("body", {})
                        .get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "Task completed.")
                    )
                else:
                    response_content = "Task completed but no results found."

                tasks = load_tasks()
                tasks[batch_id] = {
                    "description": task_description,
                    "status": "completed",
                    "result": response_content
                }
                save_tasks(tasks)
                print(f"[POLL] Job {batch_id} COMPLETED - notifying user now!", flush=True)

                # Directly speak the notification via TTS (bypasses LLM for reliability)
                await session.interrupt(force=True)
                session.say(f"Your task '{task_description}' is ready. Would you like me to read the results?")
                print(f"[POLL] Notification triggered for job {batch_id}", flush=True)
                break

            elif batch_status.status in ["failed", "expired", "cancelled"]:
                tasks = load_tasks()
                tasks[batch_id] = {
                    "description": task_description,
                    "status": batch_status.status,
                    "result": None
                }
                save_tasks(tasks)

                await session.interrupt(force=True)
                session.say(f"Sorry, your task '{task_description}' has {batch_status.status}. Would you like me to try again?")
                break

        except Exception as e:
            print(f"Error polling batch job: {e}", flush=True)
            continue
