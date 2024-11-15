

from celery import Celery
from celery.schedules import crontab
import os
from tasks import send_email_task

celery_app = Celery('tasks', broker="redis://localhost:6379/0")

celery_app.conf.update(
    beat_schedule={
        'send_email_at_2pm': {
            'task': 'tasks.send_email_task',
            'schedule': crontab(hour=14, minute=48),  
            'args': [os.environ.get("RECIPIENT_EMAIL")],
        },
    },
    timezone='Asia/Karachi'
)

