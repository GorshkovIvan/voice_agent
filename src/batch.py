import os
import json
import asyncio
from pathlib import Path
from openai import OpenAI
from livekit.agents import AgentSession

# Doubleword batch API client
batch_client = OpenAI(
    api_key=os.getenv("DOUBLEWORD_API_KEY"),
    base_url="https://api.doubleword.ai/v1"
)

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
    print(f"[POLL] Started polling for job {batch_id}")
    while True:
        await asyncio.sleep(10)
        try:
            print(f"[POLL] Checking status for job {batch_id}")
            batch_status = batch_client.batches.retrieve(batch_id)
            print(f"[POLL] Job {batch_id} status: {batch_status.status}")

            if batch_status.status == "completed":
                content = batch_client.files.content(batch_status.output_file_id)
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
                print(f"[POLL] Job {batch_id} COMPLETED - notifying user now!")

                await session.generate_reply(
                    instructions=f"INTERRUPT and tell the user: Great news! The background task '{task_description}' is now complete! Ask if they want to hear the results."
                )
                print(f"[POLL] Notification sent for job {batch_id}")
                break

            elif batch_status.status in ["failed", "expired", "cancelled"]:
                tasks = load_tasks()
                tasks[batch_id] = {
                    "description": task_description,
                    "status": batch_status.status,
                    "result": None
                }
                save_tasks(tasks)

                await session.generate_reply(
                    instructions=f"Tell the user their task '{task_description}' {batch_status.status}. Apologize and offer to try again."
                )
                break

        except Exception as e:
            print(f"Error polling batch job: {e}")
            continue
