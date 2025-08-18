# middleware/error_handler.py
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import traceback
from typing import Callable

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware for the FastAPI application
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        try:
            response = await call_next(request)
            return response
            
        except HTTPException as e:
            # Let FastAPI handle HTTP exceptions normally
            raise e
            
        except ValueError as e:
            # Handle validation errors
            logger.warning(f"Validation error on {request.url}: {str(e)}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Validation Error",
                    "message": str(e),
                    "path": str(request.url.path)
                }
            )
            
        except ConnectionError as e:
            # Handle database/Redis connection errors
            logger.error(f"Connection error on {request.url}: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service Unavailable",
                    "message": "Database connection error",
                    "path": str(request.url.path)
                }
            )
            
        except Exception as e:
            # Handle all other unexpected errors
            logger.error(f"Unexpected error on {request.url}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "path": str(request.url.path)
                }
            )