"""Vercel builds this subscriber separately from the web function."""
from vercel.queue.sync import subscribe
from backend.cloud import work, TOPIC

@subscribe(topic=TOPIC,consumer_group='signal-desk-worker',max_concurrency=1,max_attempts=5,retry_after=60)
def handle(message):
    work(message)
