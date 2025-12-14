"""Service for logging publishing run events."""
from __future__ import annotations

from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from agent.db.models import PublishingRunEvent


class PublishingRunEventService:
    """Service for logging events to publishing_run_events table."""
    
    # Standard event types
    EVENT_RUN_SCHEDULED = "RUN_SCHEDULED"
    EVENT_RUN_STARTED = "RUN_STARTED"
    EVENT_RUN_COMPLETED = "RUN_COMPLETED"
    EVENT_RUN_FAILED = "RUN_FAILED"
    EVENT_PROVIDER_ERROR = "PROVIDER_ERROR"
    EVENT_PROVIDER_ALLOCATED = "PROVIDER_ALLOCATED"
    EVENT_STATUS_CHANGE = "STATUS_CHANGE"
    
    # Provider-specific error codes
    ERROR_GOLOGIN_LIMIT = "GOLOGIN_LIMIT"
    ERROR_GOLOGIN_AUTH = "GOLOGIN_AUTH_FAILED"
    ERROR_GOLOGIN_PROFILE = "GOLOGIN_PROFILE_ERROR"
    ERROR_NOVNC_CONNECTION = "NOVNC_CONNECTION_FAILED"
    ERROR_NO_PROVIDER = "NO_PROVIDER_AVAILABLE"
    
    @staticmethod
    def log_event(
        session: Session,
        *,
        publishing_run_id: int,
        event_type: str,
        publishing_post_id: Optional[int] = None,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        error_code: Optional[str] = None,
        message: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        worker_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        actor_user_id: Optional[int] = None,
    ) -> PublishingRunEvent:
        """Log an event to the publishing_run_events table."""
        event = PublishingRunEvent(
            publishing_run_id=publishing_run_id,
            publishing_post_id=publishing_post_id,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            error_code=error_code,
            message=message,
            payload=payload,
            worker_id=worker_id,
            trace_id=trace_id,
            actor_user_id=actor_user_id,
        )
        session.add(event)
        session.commit()
        session.refresh(event)
        return event
    
    @staticmethod
    def log_provider_allocated(
        session: Session,
        publishing_run_id: int,
        provider_code: str,
        profile_id: int,
        profile_ref: str,
    ) -> PublishingRunEvent:
        """Log when a browser provider is allocated to a run."""
        return PublishingRunEventService.log_event(
            session,
            publishing_run_id=publishing_run_id,
            event_type=PublishingRunEventService.EVENT_PROVIDER_ALLOCATED,
            message=f"Allocated {provider_code} profile {profile_ref}",
            payload={
                "provider_code": provider_code,
                "browser_provider_profile_id": profile_id,
                "provider_profile_ref": profile_ref,
            }
        )
    
    @staticmethod
    def log_provider_error(
        session: Session,
        publishing_run_id: int,
        error_code: str,
        message: str,
        provider_code: Optional[str] = None,
        profile_ref: Optional[str] = None,
        exception_details: Optional[str] = None,
    ) -> PublishingRunEvent:
        """Log a browser provider error."""
        payload = {}
        if provider_code:
            payload["provider_code"] = provider_code
        if profile_ref:
            payload["provider_profile_ref"] = profile_ref
        if exception_details:
            payload["exception"] = exception_details[:1000]  # Truncate
        
        return PublishingRunEventService.log_event(
            session,
            publishing_run_id=publishing_run_id,
            event_type=PublishingRunEventService.EVENT_PROVIDER_ERROR,
            error_code=error_code,
            message=message,
            payload=payload if payload else None,
        )
    
    @staticmethod
    def log_run_started(
        session: Session,
        publishing_run_id: int,
        publishing_post_id: Optional[int] = None,
    ) -> PublishingRunEvent:
        """Log when a run starts execution."""
        return PublishingRunEventService.log_event(
            session,
            publishing_run_id=publishing_run_id,
            publishing_post_id=publishing_post_id,
            event_type=PublishingRunEventService.EVENT_RUN_STARTED,
            new_status="RUNNING",
        )
    
    @staticmethod
    def log_run_completed(
        session: Session,
        publishing_run_id: int,
        publishing_post_id: Optional[int] = None,
        result_payload: Optional[Dict[str, Any]] = None,
    ) -> PublishingRunEvent:
        """Log successful run completion."""
        return PublishingRunEventService.log_event(
            session,
            publishing_run_id=publishing_run_id,
            publishing_post_id=publishing_post_id,
            event_type=PublishingRunEventService.EVENT_RUN_COMPLETED,
            new_status="SUCCESS",
            payload=result_payload,
        )
    
    @staticmethod
    def log_run_failed(
        session: Session,
        publishing_run_id: int,
        error_message: str,
        publishing_post_id: Optional[int] = None,
        error_code: Optional[str] = None,
    ) -> PublishingRunEvent:
        """Log run failure."""
        return PublishingRunEventService.log_event(
            session,
            publishing_run_id=publishing_run_id,
            publishing_post_id=publishing_post_id,
            event_type=PublishingRunEventService.EVENT_RUN_FAILED,
            new_status="FAILED",
            error_code=error_code,
            message=error_message,
        )
