"""Automated Background Health Auditor for RAG Knowledge Base Catalogs."""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.utils.link_validator import LinkValidator
from app.utils.link_replacer import LinkReplacer
from app.utils.logger import logger
from app.utils.datetime_utils import get_utc_timestamp

CATALOG_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "catalog")

# In-memory cached result for lightning-fast inspection
LATEST_AUDIT_REPORT: Dict[str, Any] = {
    "status": "not_started",
    "timestamp": None,
    "total_resources": 0,
    "healthy_count": 0,
    "broken_count": 0,
    "broken_details": []
}

class CatalogHealthAuditor:
    """Audits and self-heals links across all RAG JSON catalogs."""

    def __init__(self):
        self.validator = LinkValidator()
        self.replacer = LinkReplacer()

    async def audit_all_catalogs(self, auto_suggest_replacements: bool = True) -> Dict[str, Any]:
        """Audit all URLs across all domain catalogs concurrently."""
        global LATEST_AUDIT_REPORT

        if not os.path.exists(CATALOG_DIR):
            logger.warning(f"Catalog directory not found at {CATALOG_DIR}")
            return {"error": "Catalog directory not found"}

        resources_to_check: List[Dict[str, Any]] = []

        # 1. Gather all resources across catalogs
        for filename in os.listdir(CATALOG_DIR):
            if filename.endswith(".json"):
                if any(x in filename for x in ["interview", "phrasing", "taxonomy", "transition_bridge"]):
                    continue
                filepath = os.path.join(CATALOG_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for item in data:
                        url = item.get("url")
                        if url and url.startswith("http"):
                            resources_to_check.append({
                                "id": item.get("id"),
                                "title": item.get("title"),
                                "url": url,
                                "domain": item.get("domain", "tech"),
                                "type": item.get("type", "course"),
                                "catalog_file": filename
                            })
                except Exception as e:
                    logger.error(f"Error reading catalog {filename} during health audit: {e}")

        total = len(resources_to_check)
        if total == 0:
            return {"status": "empty", "total_resources": 0}

        # 2. Concurrently validate all URLs
        unique_urls = list({r["url"] for r in resources_to_check})
        logger.info(f"🔍 Starting RAG Catalog Health Audit for {len(unique_urls)} unique URLs across {total} resources...")
        
        validation_results = await self.validator.validate_many(unique_urls)

        healthy_count = 0
        broken_details: List[Dict[str, Any]] = []

        for r in resources_to_check:
            url = r["url"]
            res = validation_results.get(url, {})
            status_code = res.get("status_code")
            status_str = res.get("status", "unknown")

            # Healthy if 200/300 or allowed auth redirects
            is_healthy = status_code in [200, 301, 302, 401, 403, 405] and status_str != "error"

            if is_healthy:
                healthy_count += 1
            else:
                broken_entry = {
                    "id": r["id"],
                    "title": r["title"],
                    "broken_url": url,
                    "catalog_file": r["catalog_file"],
                    "status_code": status_code,
                    "error_reason": status_str
                }
                if auto_suggest_replacements:
                    canonical = self.replacer.synthesize_canonical_search_url(r["title"], r["type"])
                    broken_entry["suggested_replacement"] = canonical

                broken_details.append(broken_entry)

        broken_count = len(broken_details)
        health_percentage = round((healthy_count / total) * 100, 1) if total > 0 else 100.0

        report = {
            "status": "healthy" if broken_count == 0 else "needs_attention",
            "timestamp": get_utc_timestamp(),
            "total_resources": total,
            "unique_urls_checked": len(unique_urls),
            "healthy_count": healthy_count,
            "broken_count": broken_count,
            "health_percentage": f"{health_percentage}%",
            "broken_details": broken_details
        }

        LATEST_AUDIT_REPORT = report

        # 3. Optional persistence in Redis
        try:
            from app.utils.redis_client import RedisClient
            redis = RedisClient()
            if await redis.ping():
                await redis.set("friction:rag_catalog_health_latest", json.dumps(report), expire=86400 * 7)
        except Exception as e:
            logger.debug(f"Redis cache write for health audit skipped: {e}")

        logger.info(f"✅ RAG Catalog Health Audit finished: {healthy_count}/{total} healthy ({health_percentage}%), {broken_count} flagged.")
        return report

async def get_latest_audit_report() -> Dict[str, Any]:
    """Retrieve the most recent audit report from memory or Redis."""
    global LATEST_AUDIT_REPORT
    if LATEST_AUDIT_REPORT.get("timestamp"):
        return LATEST_AUDIT_REPORT

    try:
        from app.utils.redis_client import RedisClient
        redis = RedisClient()
        if await redis.ping():
            raw = await redis.get("friction:rag_catalog_health_latest")
            if raw:
                data = json.loads(raw)
                LATEST_AUDIT_REPORT = data
                return data
    except Exception:
        pass

    return LATEST_AUDIT_REPORT

