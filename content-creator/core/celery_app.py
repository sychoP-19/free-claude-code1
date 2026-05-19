from celery import Celery

# Celery configuration: use Redis as broker and backend
celery = Celery(
    "content_creator",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

# Optional: define task routing if needed
celery.conf.task_routes = {
    "agents.cinema_director.run": {"queue": "video"},
}
