"""AI client wrapper with deterministic settings."""
import asyncio
import time
from typing import List, Optional, Dict, Any
# from google import genai
# from google.genai import types
from mistralai.async_client import MistralAsyncClient
from mistralai.models.chat_completion import ChatMessage
from app.config import settings
from app.utils.logger import logger
from app.utils.exceptions import LLMTruncationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

import httpx
# Monkey patch httpx to disable SSL verification (for corporate proxy environments)
_original_async_client = httpx.AsyncClient
class UnverifiedAsyncClient(_original_async_client):
    def __init__(self, *args, **kwargs):
        kwargs['verify'] = False
        super().__init__(*args, **kwargs)
httpx.AsyncClient = UnverifiedAsyncClient

class GenAIClient:
    """Wrapper around AI SDK with deterministic settings."""

    def __init__(self):
        # GEMINI CONFIGURATION (Commented out for future use)
        # if not settings.google_api_key:
        #     raise ValueError("GOOGLE_API_KEY not set")
        # self.client = genai.Client(api_key=settings.google_api_key)

        # MISTRAL CONFIGURATION
        if not settings.mistral_api_key:
            raise ValueError("MISTRAL_API_KEY not set")
        endpoint_val = getattr(settings, "mistral_endpoint", "https://api.mistral.ai")
        self.endpoint = endpoint_val if isinstance(endpoint_val, str) else "https://api.mistral.ai"
        if settings.mistral_api_key and str(settings.mistral_api_key).startswith("mstrl_") and "codestral" not in self.endpoint:
            logger.warning(
                f"mstrl_ key detected with non-codestral endpoint ({self.endpoint}). "
                "Codestral keys typically only authenticate against https://codestral.mistral.ai."
            )
        self.client = MistralAsyncClient(api_key=settings.mistral_api_key, endpoint=self.endpoint)

        self.max_retries = settings.ai_max_retries
        self.timeout = settings.ai_timeout_seconds

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 8192
    ) -> str:
        """Generate content using AI model with low temperature."""
        from urllib.parse import urlparse
        resolved_model = model or settings.ai_model or "mistral-small-latest"
        host = urlparse(self.endpoint).hostname or self.endpoint
        try:
            logger.info(f"Calling endpoint {host} with model {resolved_model} (temperature: {temperature})")
            start_time = time.time()

            response = await self.client.chat(
                model=resolved_model,
                messages=[ChatMessage(role="user", content=prompt)],
                temperature=temperature,
                max_tokens=max_output_tokens
            )

            elapsed = (time.time() - start_time) * 1000
            resp_model = getattr(response, "model", resolved_model)
            logger.info(f"Response received from model {resp_model} in {elapsed:.0f}ms")

            if hasattr(response, "usage") and response.usage:
                completion_tokens = getattr(response.usage, "completion_tokens", 0)
                logger.info(f"LLM token usage: completion_tokens={completion_tokens}")
            else:
                completion_tokens = 0

            if not response.choices or not response.choices[0].message.content:
                raise ValueError("No content returned from API")

            choice = response.choices[0]
            finish_reason = getattr(choice, "finish_reason", None)
            if finish_reason in ["length", "model_length"]:
                logger.warning(
                    f"LLM response truncated by model: finish_reason='{finish_reason}', "
                    f"completion_tokens={completion_tokens}"
                )
                raise LLMTruncationError(
                    f"LLM response was truncated due to length limit (finish_reason='{finish_reason}')",
                    completion_tokens=completion_tokens
                )

            return choice.message.content

        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            raise

    async def generate_structured_content(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate structured JSON response with low temperature."""
        import json
        import re

        # Add schema instruction to prompt
        json_prompt = f"""
        {prompt}

        IMPORTANT: Return ONLY valid JSON that matches this schema:
        {json.dumps(output_schema, indent=2)}

        Do not include any other text, markdown, or explanations.
        Return ONLY the JSON object, nothing else.
        """

        response_text = await self.generate_content(
            prompt=json_prompt,
            model=model,
            temperature=temperature
        )

        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response: {response_text[:500]}...")
            raise ValueError("Invalid JSON response from AI")
