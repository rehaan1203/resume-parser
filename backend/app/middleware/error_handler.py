"""Global exception handlers."""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.utils.logger import logger
import traceback

def add_error_handlers(app: FastAPI):
    """Register global exception handlers."""
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors."""
        logger.warning(f"Validation error: {exc.errors()}")
        
        clean_errors = []
        for error in exc.errors():
            clean_error = dict(error)
            if 'ctx' in clean_error and 'error' in clean_error['ctx']:
                clean_error['ctx']['error'] = str(clean_error['ctx']['error'])
            clean_errors.append(clean_error)
            
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Validation error",
                "errors": clean_errors
            }
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions."""
        logger.error(f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred",
                "error_type": type(exc).__name__
            }
        )
