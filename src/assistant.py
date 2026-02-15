import os
import json
import asyncio
import time
import tempfile
from livekit.agents import Agent, function_tool

from .batch import batch_client, poll_batch_job, load_tasks, save_tasks, _background_tasks

SYSTEM_PROMPT = """You are a helpful voice assistant.
Keep ALL responses short — 2 to 3 sentences maximum. This is a voice conversation, not a written essay.
Avoid complex formatting, bullet points, or special characters.

When the user interrupts you or asks you to stop/calm down, immediately acknowledge it and stop talking about the previous topic. Always prioritize the user's latest message over continuing your previous response.

IMPORTANT: For complex tasks requiring detailed work such as:
- Creating business plans, marketing plans, or strategies
- Writing long documents, reports, or analyses
- Detailed research or comprehensive summaries
- Any task that would require more than 2-3 sentences to answer properly

You MUST use the submit_batch_task tool to offload the work.
Tell the user you're submitting their request and they'll be notified when ready.
Do NOT attempt these complex tasks yourself - always use the batch tool.

When a task completes, use get_task_result to read the full results.

For simple questions and short conversations, respond normally but keep it brief."""


class VoiceAssistant(Agent):
    def __init__(self, session_ref: list) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self._session_ref = session_ref
        self._last_submission_time: float = 0  # timestamp of last batch submission

    @function_tool
    async def submit_batch_task(self, task_description: str, detailed_prompt: str) -> str:
        """Submit a complex task to the batch processing API for thorough completion.

        Args:
            task_description: Brief description of the task (e.g., "business plan for coffee shop")
            detailed_prompt: Full detailed prompt with all context and requirements for the task
        """
        try:
            # Prevent duplicate submissions after speech interruption
            now = time.time()
            if now - self._last_submission_time < 60:
                return f"A task was already submitted recently. Please wait for it to complete."
            self._last_submission_time = now

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
                batch_file = await batch_client.files.create(file=f, purpose="batch")

            batch = await batch_client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="1h"
            )

            tasks = load_tasks()
            tasks[batch.id] = {
                "description": task_description,
                "status": "processing",
                "result": None
            }
            save_tasks(tasks)

            if self._session_ref and self._session_ref[0]:
                task = asyncio.create_task(poll_batch_job(batch.id, self._session_ref[0], task_description))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

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
