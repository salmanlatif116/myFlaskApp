from app import app, send_email_with_attachment
from celery import Celery

celery_app = Celery('tasks', broker="redis://localhost:6379/0")

@celery_app.task
def send_email_task(recipient):
    with app.app_context():
        send_email_with_attachment(recipient)
