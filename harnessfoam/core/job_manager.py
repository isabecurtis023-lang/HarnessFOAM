import asyncio
from typing import Dict, Any

class JobManager:
    def __init__(self):
        self.queues: Dict[str, asyncio.Queue] = {}
        self.tasks: Dict[str, asyncio.Task] = {}

    def get_queue(self, job_id: str) -> asyncio.Queue:
        if job_id not in self.queues:
            self.queues[job_id] = asyncio.Queue()
        return self.queues[job_id]

    async def publish(self, job_id: str, message: Dict[str, Any]):
        queue = self.get_queue(job_id)
        await queue.put(message)

    async def subscribe(self, job_id: str):
        queue = self.get_queue(job_id)
        while True:
            message = await queue.get()
            if message is None: # EOF signal
                break
            yield message

    def start_job(self, job_id: str, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self.tasks[job_id] = task
        return task

    def stop_job(self, job_id: str):
        if job_id in self.tasks:
            task = self.tasks[job_id]
            if not task.done():
                task.cancel()
            del self.tasks[job_id]
            
    async def finish_job(self, job_id: str):
        queue = self.get_queue(job_id)
        await queue.put(None)

job_manager = JobManager()
