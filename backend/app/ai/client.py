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
        self.client = MistralAsyncClient(api_key=settings.mistral_api_key)

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
        model: str = "mistral-small-latest", # <-- Changed default to mistral
        temperature: float = 0.1,  # <-- LOWERED: was 0.7, now 0.1 for consistency
        max_output_tokens: int = 8192
    ) -> str:
        """Generate content using AI model with low temperature."""
        try:
            logger.info(f"Generating content with {model} (temperature: {temperature})")
            start_time = time.time()

            # GEMINI IMPLEMENTATION (Commented out for future use)
            # response = await asyncio.to_thread(
            #     self.client.models.generate_content,
            #     model=model,
            #     contents=prompt,
            #     config=types.GenerateContentConfig(
            #         temperature=temperature,
            #         max_output_tokens=max_output_tokens,
            #     )
            # )
            # if response.text:
            #     return response.text
            # else:
            #     raise ValueError("No content returned from API")

            # MISTRAL IMPLEMENTATION
            # If the user asks for gemini, fallback to mistral for now
            if "gemini" in model:
                model = "mistral-small-latest"
                
            response = await self.client.chat(
                model=model,
                messages=[ChatMessage(role="user", content=prompt)],
                temperature=temperature,
                max_tokens=max_output_tokens
            )

            elapsed = (time.time() - start_time) * 1000
            logger.info(f"Content generated in {elapsed:.0f}ms")

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            else:
                raise ValueError("No content returned from API")

        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            raise

    async def generate_structured_content(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        model: str = "mistral-small-latest", # <-- Changed default to mistral
        temperature: float = 0.1  # <-- LOWERED: was 0.3, now 0.1
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
