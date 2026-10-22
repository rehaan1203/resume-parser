"""Configuration management with Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import List, Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)
    
    # Application
    app_name: str = "Friction Matcher API"
    app_version: str = "0.1.0"
    debug: bool = True
    log_level: str = "INFO"
    
    # Server
    host: str = "0.0.0.0"
    port: int
    workers: int = 1
    
    # CORS
    cors_origins: List[str]
    
    # API
    api_prefix: str = "/api/v1"
    
    # AI Service
    google_api_key: Optional[str] = None
    mistral_api_key: Optional[str] = None
    huggingfacehub_api_token: Optional[str] = None
    hf_hub_offline: str = "0"
    ai_model: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    embedding_model: str = "gemini-embedding-2"
    use_ai_service: bool = True
    ai_max_retries: int = 3
    ai_timeout_seconds: int = 45
    ai_backoff_factor: float = 2.0
    max_embedding_batch_size: int = 100
    max_token_limit: int = 8000
    
    # Critic Loop Settings
    critic_enabled: bool = True
    critic_max_retries: int = 3
    critic_backoff_factor: float = 2.0
    critic_fallback_to_mock: bool = True
    critic_score_penalty_domain: int = 15
    
    # Tools
    tools_enabled: bool = True

    # Scoring & Evidence Settings
    low_evidence_threshold: int = 3

    # Tavily API
    tavily_api_key: Optional[str] = None
    tavily_search_limit: int = 3

    # YouTube API
    youtube_api_key: Optional[str] = None
    youtube_search_limit: int = 3

    # Link Verification
    link_verification_enabled: bool = True
    link_verification_timeout: float = 5.0
    link_replacement_enabled: bool = True
    max_link_retries: int = 2
    link_verification_max_concurrent: int = 10
    link_verification_retry_attempts: int = 3
    link_verification_backoff_factor: float = 2.0
    link_verification_skip_major_platforms: bool = True
    link_verification_cache_ttl: int = 3600

    # Privacy (internal)
    privacy_scrub_enabled: bool = True
    
    # Level 3: Self-Correction
    self_correction_enabled: bool = True
    max_iterations: int = 3
    quality_threshold: int = 85

    # Learning Memory
    learning_memory_enabled: bool = True
    learning_store_type: str = "file"  # or "redis"
    learning_store_path: str = "./data/learning_memory.json"
    
    # Level 4: Tree of Thoughts
    tree_of_thoughts_enabled: bool = True
    num_plans: int = 3
    plan_evaluation_accuracy_weight: float = 0.4
    plan_evaluation_efficiency_weight: float = 0.2
    plan_evaluation_robustness_weight: float = 0.2
    plan_evaluation_interpretability_weight: float = 0.2
    plan_selection_threshold: int = 70
    fallback_to_level3: bool = True

    # Level 5: Multi-Agent Collaboration
    multi_agent_enabled: bool = True
    parallel_agent_execution: bool = True
    max_agent_retries: int = 2
    domain_agent_timeout: int = 10
    skills_agent_timeout: int = 15
    scorer_agent_timeout: int = 10
    critic_agent_timeout: int = 10
    roadmap_agent_timeout: int = 15

    # Level 6: Continuous Learning
    continuous_learning_enabled: bool = True
    feedback_collection_enabled: bool = True
    pattern_extraction_enabled: bool = True
    knowledge_retrieval_enabled: bool = True
    max_patterns_per_type: int = 100
    learning_store_path: str = "./data/learning_memory.json"
    feedback_min_rating: int = 1
    feedback_max_rating: int = 5
    implicit_feedback_enabled: bool = True
    learning_update_interval_hours: int = 24
    performance_tracking_enabled: bool = True
    track_accuracy_trend: bool = True
    accuracy_window_days: int = 30
    
    # Redis Cloud
    redis_url: Optional[str] = None
    redis_host: Optional[str] = None
    redis_port: Optional[int] = None
    redis_username: Optional[str] = None
    redis_password: Optional[str] = None
    redis_ssl: bool = False
    redis_pool_size: int = 10
    redis_socket_timeout: int = 5
    redis_socket_connect_timeout: int = 5
    redis_default_ttl: int = 300
    redis_session_ttl: int = 86400
    redis_file_ttl: int = 86400
    redis_cache_ttl: int = 3600
    
    # Cache TTLs
    cache_ttl_embeddings: int = 3600  # 1 hour
    cache_ttl_analysis: int = 86400   # 24 hours
    cache_ttl_jd: int = 604800        # 7 days
    cache_ttl_session: int = 3600     # 1 hour
    
    # Cache Settings
    cache_enabled: bool = True
    cache_warmup_enabled: bool = True
    cache_max_entries: int = 1000
    
    # Rate Limiting (Phase 4/5)
    rate_limit_per_minute: int = 10
    rate_limit_per_day: int = 100
    
    # Timeouts
    query_timeout_seconds: int = 10
    sql_execution_timeout: int = 5
    ai_response_timeout: int = 15
    
    # Conditional Sections
    conditional_sections_enabled: bool = True
    match_high_threshold: int = 60
    match_partial_threshold: int = 20
    match_low_threshold: int = 0

    # Domain Detection
    domain_detection_enabled: bool = True
    domain_unknown_threshold: int = 10

    # Gap Analysis
    gap_mini_upskill_threshold: int = 90
    gap_short_upskill_threshold: int = 70
    gap_standard_upskill_threshold: int = 50

    # Resources
    max_resources_per_domain: int = 5
    include_youtube_resources: bool = True
    include_certification_resources: bool = True

    # Timeline Calculation
    timeline_30_day_max: int = 30
    timeline_90_day_max: int = 120
    timeline_transition_min: int = 12
    timeline_transition_max: int = 24
    
    @model_validator(mode='after')
    def validate_api_key(self):
        """Require API key if AI service is enabled."""
        if self.use_ai_service and not (self.google_api_key or self.mistral_api_key):
            raise ValueError("Either GOOGLE_API_KEY or MISTRAL_API_KEY required when USE_AI_SERVICE=true")
        if self.tools_enabled and not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY required when TOOLS_ENABLED=true")
        return self

settings = Settings()
