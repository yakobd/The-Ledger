# src/mcp/errors.py
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

class McpErrorDetail(BaseModel):
    error_type: str
    message: str
    suggested_action: str | None = None
    context: dict = Field(default_factory=dict)

async def mcp_exception_handler(request: Request, exc: Exception):
    from src.event_store import OptimisticConcurrencyError # Avoid circular import

    if isinstance(exc, OptimisticConcurrencyError):
        error_detail = McpErrorDetail(
            error_type="OptimisticConcurrencyError",
            message=str(exc),
            suggested_action="Reload stream and retry command.",
            context={'stream_id': exc.stream_id, 'expected': exc.expected_version, 'actual': exc.actual_version}
        )
        return JSONResponse(status_code=409, content=error_detail.model_dump()) # 409 Conflict
    
    if isinstance(exc, ValueError): # For domain errors
        error_detail = McpErrorDetail(
            error_type="PreconditionFailed",
            message=str(exc),
            suggested_action="Review agent logic and tool preconditions."
        )
        return JSONResponse(status_code=400, content=error_detail.model_dump())
    
    # Default for all other errors
    error_detail = McpErrorDetail(
        error_type="InternalServerError",
        message="An unexpected internal error occurred."
    )
    return JSONResponse(status_code=500, content=error_detail.model_dump())
