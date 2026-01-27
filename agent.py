import os
import json
import asyncio
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, function_tool
from livekit.plugins import anthropic, elevenlabs, silero

load_dotenv()

# Doubleword batch API client
batch_client = OpenAI(
    api_key=os.getenv("DOUBLEWORD_API_KEY"),
    base_url="https://api.doubleword.ai/v1"
)

# File to store task results
TASKS_FILE = Path(__file__).parent / "tasks_results.json"


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
        await asyncio.sleep(10)  # Poll every 10 seconds for faster response
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

                # Save to file
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


class VoiceAssistant(Agent):
    def __init__(self, session_ref: list) -> None:
        super().__init__(
            instructions="""You are a helpful voice assistant.
Keep your responses concise and conversational.
Avoid complex formatting, bullet points, or special characters.

IMPORTANT: For complex tasks requiring detailed work such as:
- Creating business plans, marketing plans, or strategies
- Writing long documents, reports, or analyses
- Detailed research or comprehensive summaries
- Any task that would require more than 2-3 sentences to answer properly

You MUST use the submit_batch_task tool to offload the work.
Tell the user you're submitting their request and they'll be notified when ready.
Do NOT attempt these complex tasks yourself - always use the batch tool.

When a task completes, use get_task_result to read the full results.

For simple questions and short conversations, respond normally."""
        )
        self._session_ref = session_ref

    @function_tool
    async def submit_batch_task(self, task_description: str, detailed_prompt: str) -> str:
        """Submit a complex task to the batch processing API for thorough completion.

        Args:
            task_description: Brief description of the task (e.g., "business plan for coffee shop")
            detailed_prompt: Full detailed prompt with all context and requirements for the task
        """
        try:
            batch_request = {
                "custom_id": f"task-{len(load_tasks()) + 1}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": os.getenv("BATCH_MODEL", "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8"),
                    "messages": [
                        {"role": "system", "content": "You are a professional assistant. Complete the task thoroughly and professionally."},
                        {"role": "user", "content": detailed_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 4096
                }
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                f.write(json.dumps(batch_request) + '\n')
                temp_path = f.name

            with open(temp_path, 'rb') as f:
                batch_file = batch_client.files.create(file=f, purpose="batch")

            batch = batch_client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="1h"
            )

            # Save initial task state
            tasks = load_tasks()
            tasks[batch.id] = {
                "description": task_description,
                "status": "processing",
                "result": None
            }
            save_tasks(tasks)

            if self._session_ref and self._session_ref[0]:
                asyncio.create_task(poll_batch_job(batch.id, self._session_ref[0], task_description))

            os.unlink(temp_path)

            return f"Task '{task_description}' submitted successfully. Job ID: {batch.id}. The user will be notified when complete."

        except Exception as e:
            return f"Failed to submit task: {str(e)}"

    @function_tool
    async def check_task_status(self) -> str:
        """Check the status of all submitted batch tasks."""
        tasks = load_tasks()
        if not tasks:
            return "No tasks found."

        statuses = []
        for job_id, task in tasks.items():
            statuses.append(f"Job {job_id}: {task['description']} - {task['status']}")
        return "Tasks:\n" + "\n".join(statuses)

    @function_tool
    async def get_task_result(self, job_id: str) -> str:
        """Get the full result of a completed batch task.

        Args:
            job_id: The job ID of the task to retrieve results for
        """
        tasks = load_tasks()
        if job_id not in tasks:
            return f"No task found with job ID: {job_id}"

        task = tasks[job_id]
        if task["status"] != "completed":
            return f"Task '{task['description']}' is still {task['status']}. Please wait."

        if task["result"]:
            return f"Results for '{task['description']}':\n\n{task['result']}"
        else:
            return "Task completed but no results were saved."


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
