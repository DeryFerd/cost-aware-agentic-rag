"""FastAPI middleware for trace IDs."""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

_TRACE_ID_HEADER = "X-Trace-ID"


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Middleware that generates a unique trace ID for every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = request.headers.get(_TRACE_ID_HEADER) or uuid.uuid4().hex
        request.state.trace_id = trace_id

        logger.info(
            "trace_id=%s method=%s path=%s",
            trace_id,
            request.method,
            request.url.path,
        )

        response = await call_next(request)
        response.headers[_TRACE_ID_HEADER] = trace_id
        return response
