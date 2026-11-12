"""AI client wrapper with deterministic settings."""
import asyncio
import contextvars
import time
from typing import List, Optional, Dict, Any
# from google import genai
# from google.genai import types
from mistralai.async_client import MistralAsyncClient
from mistralai.models.chat_completion import ChatMessage
from app.config import settings
from app.utils.logger import logger
from app.utils.exceptions import LLMTruncationError
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_not_exception_type

import httpx

# Execution priority context: interactive UI calls preempt background Outlook batches
llm_priority_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("llm_priority", default="interactive")


class GenAIClient:
    """Wrapper around AI SDK with deterministic settings."""
    _request_semaphore: Optional[asyncio.Semaphore] = None
    _last_request_time: float = 0.0
    _min_request_gap: float = 2.5  # Safe post-completion spacing for Mistral Experiment-tier RPM/TPM bursts
    _interactive_waiters: int = 0  # Tracks active interactive UI callers so background batches yield
    _groq_unavailable: bool = False  # Circuit breaker if Groq key lacks model access or fails auth
    _resolved_groq_model: Optional[str] = None
    _mistral_cooldown_until: float = 0.0  # Temporary cooldown window after Mistral 429
    _shared_groq_http_client: Optional[httpx.AsyncClient] = None
    _shared_mistral_http_client: Optional[httpx.AsyncClient] = None

    @classmethod
    def _get_semaphore(cls) -> asyncio.Semaphore:
        if cls._request_semaphore is None:
            cls._request_semaphore = asyncio.Semaphore(1)
        return cls._request_semaphore

    @classmethod
    def _get_groq_http_client(cls, timeout: int) -> httpx.AsyncClient:
        if cls._shared_groq_http_client is None or cls._shared_groq_http_client.is_closed:
            cls._shared_groq_http_client = httpx.AsyncClient(
                verify=getattr(settings, "ai_ssl_verify", False),
                timeout=timeout,
            )
        return cls._shared_groq_http_client

    @classmethod
    def _get_mistral_http_client(cls, timeout: int) -> httpx.AsyncClient:
        if cls._shared_mistral_http_client is None or cls._shared_mistral_http_client.is_closed:
            cls._shared_mistral_http_client = httpx.AsyncClient(
                verify=getattr(settings, "ai_ssl_verify", False),
                follow_redirects=True,
                timeout=timeout,
                limits=httpx.Limits(max_connections=64),
                transport=httpx.AsyncHTTPTransport(retries=1),
            )
        return cls._shared_mistral_http_client

    @classmethod
    async def close_shared(cls) -> None:
        """Close pooled LLM HTTP clients gracefully during application shutdown."""
        for attr in ("_shared_groq_http_client", "_shared_mistral_http_client"):
            hc = getattr(cls, attr, None)
            if hc is not None and not hc.is_closed:
                try:
                    await hc.aclose()
                except Exception:
                    pass
                setattr(cls, attr, None)

    def __init__(self):
        # GEMINI CONFIGURATION (Commented out for future use)
        # if not settings.google_api_key:
        #     raise ValueError("GOOGLE_API_KEY not set")
        # self.client = genai.Client(api_key=settings.google_api_key)

        self.max_retries = settings.ai_max_retries
        self.timeout = settings.ai_timeout_seconds

        # GROQ CONFIGURATION (reuses shared proxy-tolerant httpx client without mutating global httpx.AsyncClient)
        self.groq_client = None
        if getattr(settings, "groq_api_key", None):
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(
                    api_key=settings.groq_api_key,
                    http_client=self._get_groq_http_client(self.timeout),
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Groq client: {e}")

        # MISTRAL CONFIGURATION
        self.client = None
        self.endpoint = "https://api.mistral.ai"
        if settings.mistral_api_key:
            endpoint_val = getattr(settings, "mistral_endpoint", "https://api.mistral.ai")
            self.endpoint = endpoint_val if isinstance(endpoint_val, str) else "https://api.mistral.ai"
            if str(settings.mistral_api_key).startswith("mstrl_") and "codestral" not in self.endpoint:
                logger.warning(
                    f"mstrl_ key detected with non-codestral endpoint ({self.endpoint}). "
                    "Codestral keys typically authenticate against https://codestral.mistral.ai."
                )
            self.client = MistralAsyncClient(api_key=settings.mistral_api_key, endpoint=self.endpoint, max_retries=1)
            # Reuse pooled verify=False httpx client strictly on Mistral's internal client
            internal_client = getattr(self.client, "_client", None)
            if isinstance(internal_client, httpx.AsyncClient):
                self.client._client = self._get_mistral_http_client(self.timeout)
        elif not self.groq_client:
            raise ValueError("Neither MISTRAL_API_KEY nor GROQ_API_KEY is configured")

    async def _call_groq(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 8192,
    ) -> str:
        """Execute chat completion via Groq API with model probing and 404 circuit breaker."""
        configured = getattr(settings, "groq_model", "llama-3.3-70b-versatile")
        candidates: List[str] = []
        if model and any(m in model.lower() for m in ["llama", "mixtral", "groq", "qwen"]):
            candidates.append(model)
        elif GenAIClient._resolved_groq_model:
            candidates.append(GenAIClient._resolved_groq_model)
        else:
            for m in ["openai/gpt-oss-120b", configured, "llama-3.1-8b-instant", "qwen/qwen3-32b"]:
                if m and m not in candidates:
                    candidates.append(m)

        last_err: Optional[Exception] = None
        for candidate_model in candidates:
            try:
                logger.info(f"Calling Groq API with model {candidate_model} (temperature: {temperature})")
                start_time = time.time()
                completion = await self.groq_client.chat.completions.create(
                    model=candidate_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_output_tokens
                )
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"Groq response received in {elapsed:.0f}ms")
                if completion.choices and completion.choices[0].message.content:
                    GenAIClient._resolved_groq_model = candidate_model
                    return completion.choices[0].message.content
                raise ValueError("Empty response returned from Groq API")
            except Exception as e:
                last_err = e
                err_low = str(e).lower()
                if "404" in err_low or "model_not_found" in err_low or "does not exist" in err_low:
                    logger.warning(f"Groq model '{candidate_model}' unavailable (404); trying next fallback if any.")
                    continue
                raise

        # All Groq models returned 404 or failed auth -> trip circuit breaker so retries stay on Mistral
        GenAIClient._groq_unavailable = True
        logger.warning("No accessible Groq models found; disabling Groq failover for this session.")
        if last_err:
            raise last_err
        raise RuntimeError("Groq failover failed with no available models.")

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_random_exponential(multiplier=2.0, min=3, max=14),
        retry=retry_if_not_exception_type(LLMTruncationError),
        reraise=True
    )
    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 8192
    ) -> str:
        """Generate content using AI model with concurrency pacing and resilient Groq failover."""
        from urllib.parse import urlparse
        resolved_model = model or settings.ai_model or "mistral-small-latest"

        is_background = llm_priority_ctx.get() == "background"
        if is_background:
            # Yield gracefully while live frontend UI requests are waiting for the LLM semaphore
            waited = 0.0
            while GenAIClient._interactive_waiters > 0 and waited < 30.0:
                await asyncio.sleep(0.25)
                waited += 0.25
        else:
            GenAIClient._interactive_waiters += 1

        try:
            # Concurrency and pacing guard: serialize requests and enforce post-completion spacing
            async with self._get_semaphore():
                now = time.time()
                elapsed_since_last = now - GenAIClient._last_request_time
                if GenAIClient._last_request_time > 0 and elapsed_since_last < GenAIClient._min_request_gap:
                    await asyncio.sleep(GenAIClient._min_request_gap - elapsed_since_last)

                try:
                    # Direct Groq route if requested, Mistral unavailable, or Mistral in post-429 cooldown
                    mistral_cooling_down = time.time() < GenAIClient._mistral_cooldown_until
                    if self.groq_client and not GenAIClient._groq_unavailable and (
                        (model and any(m in model.lower() for m in ["llama", "mixtral", "groq", "qwen"]))
                        or not self.client
                        or mistral_cooling_down
                    ):
                        try:
                            return await self._call_groq(prompt, model=model, temperature=temperature, max_output_tokens=max_output_tokens)
                        except Exception as e:
                            logger.warning(f"Groq generation failed ({e}), falling back to Mistral if available.")
                            if not self.client:
                                raise

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
                        err_str = str(e).lower()
                        if ("429" in err_str or "rate" in err_str or "too many requests" in err_str):
                            GenAIClient._mistral_cooldown_until = time.time() + 20.0
                            if self.groq_client and not GenAIClient._groq_unavailable:
                                try:
                                    logger.warning("Mistral rate-limited (429); activating 20s cooldown and failing over to Groq.")
                                    return await self._call_groq(prompt, model=None, temperature=temperature, max_output_tokens=max_output_tokens)
                                except Exception as groq_err:
                                    logger.warning(f"Groq failover unsuccessful ({groq_err}); retrying Mistral after cooldown.")
                        logger.error(f"Content generation failed: {e}")
                        raise
                finally:
                    GenAIClient._last_request_time = time.time()
        finally:
            if not is_background:
                GenAIClient._interactive_waiters = max(0, GenAIClient._interactive_waiters - 1)

    @staticmethod
    def _parse_json_payload(response_text: str) -> Dict[str, Any]:
        """Extract and parse a JSON object cleanly from raw LLM output."""
        import json
        import re

        cleaned = (response_text or "").strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return json.loads(cleaned)

    async def generate_structured_content(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """Generate structured JSON response with low temperature and one format-repair retry."""
        import json

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
            return self._parse_json_payload(response_text)
        except json.JSONDecodeError as first_err:
            logger.warning(f"Malformed JSON from AI ({first_err}); retrying once at temperature=0.0")
            retry_prompt = (
                f"{json_prompt}\n\nYour previous reply was not valid RFC-8259 JSON. "
                "Output ONLY one valid JSON object with double quotes and no trailing commas."
            )
            retry_text = await self.generate_content(
                prompt=retry_prompt,
                model=model,
                temperature=0.0
            )
            try:
                return self._parse_json_payload(retry_text)
            except json.JSONDecodeError as second_err:
                logger.error(f"Failed to parse JSON response after retry: {second_err}")
                logger.error(f"Response: {(retry_text or '')[:500]}...")
                raise ValueError("Invalid JSON response from AI")
