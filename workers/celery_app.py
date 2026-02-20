import os
from celery import Celery
from kombu import Exchange, Queue

CELERY_BROKER = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery = Celery("workers", broker=CELERY_BROKER, backend=CELERY_BACKEND)

# ============ Queue Configuration ============
# Define separate queues for different task types
celery.conf.task_queues = (
    Queue("intake", Exchange("intake"), routing_key="intake", queue_arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "dead-letter"
    }),
    Queue("jobs", Exchange("jobs"), routing_key="jobs", queue_arguments={
        "x-dead-letter-exchange": "dlx",
        "x-dead-letter-routing-key": "dead-letter"
    }),
    Queue("dead-letter", Exchange("dlx"), routing_key="dead-letter"),  # Dead-letter queue
)

# ============ Task Configuration ============
celery.conf.task_routes = {
    "workers.tasks.run_job": {"queue": "jobs"},
    "workers.tasks.run_intake": {"queue": "intake"},
    "workers.tasks.run_intake_answers": {"queue": "intake"},
    "workers.tasks.run_scheduled_jobs": {"queue": "jobs"},
    "workers.tasks.check_system_alerts": {"queue": "jobs"},
}

# ============ Timeout & Retry Settings ============
celery.conf.task_soft_time_limit = 540  # 9 minutes soft timeout
celery.conf.task_time_limit = 600  # 10 minutes hard timeout
celery.conf.task_acks_late = True  # Only mark task as done after successful completion
celery.conf.worker_prefetch_multiplier = 1  # One task at a time (prevent queue overflow)
celery.conf.worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks (memory safety)

# ============ Default Retry Configuration ============
celery.conf.task_default_retry_delay = 60  # 1 minute before first retry
celery.conf.task_default_max_retries = 3  # Max 3 attempts total

# ============ Result Backend Configuration ============
celery.conf.result_expires = 3600  # Results expire after 1 hour
celery.conf.result_backend_transport_options = {
    "retry_on_timeout": True,
    "health_check_interval": 30
}

# ============ Beat Schedule ============
celery.conf.beat_schedule = {
    "run-scheduled-jobs-every-minute": {
        "task": "workers.tasks.run_scheduled_jobs",
        "schedule": 60.0,
    },
    "check-system-alerts-every-5-minutes": {
        "task": "workers.tasks.check_system_alerts",
        "schedule": 300.0,
    }
}
