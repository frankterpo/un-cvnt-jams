from agent.db.base import SessionLocal
from agent.db.models import PublishingRun, PublishingPost

def reset():
    session = SessionLocal()
    try:
        runs = session.query(PublishingRun).filter(PublishingRun.id.in_([7, 8])).all()
        for r in runs:
            r.status = "PENDING"
            r.started_at = None
            r.completed_at = None
            r.error_message = None
            # r.retry_count = 0 # Optional, let's keep retries if meaningful, but for test reset usually we clear.
        
        posts = session.query(PublishingPost).filter(PublishingPost.id.in_([7, 8])).all()
        for p in posts:
            p.status = "PENDING"
            p.started_at = None
            p.completed_at = None
            p.error_message = None

        session.commit()
        print(f"Reset {len(runs)} runs and {len(posts)} posts to PENDING.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    reset()
