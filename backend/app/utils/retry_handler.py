import asyncio
from typing import Callable, Type, TypeVar, Any, Optional
from loguru import logger
from .schema_validator import SchemaValidator
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class RetryHandler:
    """Handles retries for LLM calls with exponential backoff."""
    
    def __init__(self, max_retries: int = 3, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    async def execute_with_retry(
        self, 
        call_llm_func: Callable[[Optional[str]], Any], 
        schema_class: Type[T]
    ) -> T:
        """
        Executes an LLM call and validates the output, retrying on failure.
        
        Args:
            call_llm_func: An async function that calls the LLM and returns text.
                           It should accept an optional 'error_context' string.
            schema_class: The Pydantic model to validate against.
            
        Returns:
            The validated Pydantic model.
            
        Raises:
            Exception: If all retries fail.
        """
        error_context = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Call the LLM
                response_text = await call_llm_func(error_context)
                
                # Validate the output
                return SchemaValidator.validate(response_text, schema_class)
                
            except ValueError as e:
                # This is a validation or JSON parsing error
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} retries failed for LLM validation.")
                    raise
                
                logger.warning(f"Validation failed on attempt {attempt + 1}. Retrying...")
                error_context = str(e)
                
                # Exponential backoff
                await asyncio.sleep(self.backoff_factor ** attempt)
                
            except Exception as e:
                # This could be a network error, rate limit, etc.
                if attempt == self.max_retries:
                    logger.error(f"All {self.max_retries} retries failed due to general error: {e}")
                    raise
                
                logger.warning(f"Error calling LLM on attempt {attempt + 1}: {e}. Retrying...")
                error_context = None # Usually don't send network errors to LLM
                
                # Exponential backoff
                await asyncio.sleep(self.backoff_factor ** attempt)
