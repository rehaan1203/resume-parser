"""Safe Whitelisted Resource Ingestion Tool (Direction 3).

Validates URLs against an authority whitelist, executes async HTTP HEAD/GET probes,
ensures schema compliance, and appends verified resources to the proper domain catalog.
"""
import os
import sys
import json
import asyncio
import argparse
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import httpx

CATALOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "knowledge", "catalog")

# Whitelist of trusted high-relevance educational, documentation, and authority domains
WHITELISTED_DOMAINS = [
    "coursera.org",
    "edx.org",
    "youtube.com",
    "youtu.be",
    "github.com",
    "fastapi.tiangolo.com",
    "kubernetes.io",
    "aws.amazon.com",
    "skillbuilder.aws",
    "react.dev",
    "nextjs.org",
    "pytorch.org",
    "postgresqltutorial.com",
    "developer.hashicorp.com",
    "uspto.gov",
    "iapp.org",
    "law.cornell.edu",
    "cpr.heart.org",
    "hhs.gov",
    "ncsbn.org",
    "cdc.gov",
    "epa.gov",
    "osha.gov",
    "nfpa.org",
    "aws.org",
    "corporatefinanceinstitute.com",
    "sec.gov",
    "w3schools.com",
    "developer.mozilla.org",
    "docs.python.org"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def is_whitelisted_domain(url: str) -> bool:
    """Check if the URL hostname matches or ends with an approved domain."""
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            return False
        for domain in WHITELISTED_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                return True
        return False
    except Exception:
        return False


async def probe_url_active(url: str, timeout_seconds: float = 8.0) -> bool:
    """Verify that URL is reachable and does not return 404 or connection error."""
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(verify=False) as client:
        try:
            res = await client.head(url, headers=headers, follow_redirects=True, timeout=timeout_seconds)
            if res.status_code in (403, 405):
                res = await client.get(url, headers=headers, follow_redirects=True, timeout=timeout_seconds)
            return res.status_code < 400 or res.status_code in (403, 429)
        except Exception as e:
            print(f"URL probe error: {e}")
            return False


def add_resource_to_catalog(
    domain: str,
    resource_id: str,
    title: str,
    url: str,
    platform: str,
    resource_type: str,
    skills_covered: List[str],
    difficulty: str,
    duration_hours: float,
    is_free: bool,
    description: str,
    bypass_probe: bool = False
) -> Dict[str, Any]:
    """Validate and append a new resource entry to the target domain catalog."""
    domain_clean = domain.strip().lower()
    catalog_filename = f"{domain_clean}_catalog.json"
    catalog_path = os.path.join(CATALOG_DIR, catalog_filename)

    if not is_whitelisted_domain(url):
        raise ValueError(f"Domain for URL '{url}' is not in the trusted authority whitelist.")

    if not bypass_probe:
        is_active = asyncio.run(probe_url_active(url))
        if not is_active:
            raise ValueError(f"URL '{url}' is unreachable or returned an error status.")

    os.makedirs(CATALOG_DIR, exist_ok=True)
    existing_items: List[Dict[str, Any]] = []
    if os.path.exists(catalog_path):
        with open(catalog_path, "r", encoding="utf-8") as f:
            try:
                existing_items = json.load(f)
            except Exception:
                existing_items = []

    # Check for duplicate ID or URL
    for item in existing_items:
        if item.get("id") == resource_id:
            raise ValueError(f"Resource with ID '{resource_id}' already exists in {catalog_filename}.")
        if item.get("url") == url:
            raise ValueError(f"Resource with URL '{url}' already exists in {catalog_filename} (ID: {item.get('id')}).")

    new_item = {
        "id": resource_id,
        "title": title,
        "url": url,
        "platform": platform,
        "type": resource_type,
        "domain": domain_clean,
        "skills_covered": [s.strip().lower() for s in skills_covered],
        "difficulty": difficulty.lower(),
        "duration_hours": float(duration_hours),
        "is_free": bool(is_free),
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "health_status": "active",
        "last_checked_at": datetime.now(timezone.utc).isoformat(),
        "description": description
    }

    existing_items.append(new_item)
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(existing_items, f, indent=2)

    print(f"Successfully added '{title}' ({resource_id}) to {catalog_filename}.")
    return new_item


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a verified learning resource into RAG catalog.")
    parser.add_argument("--domain", required=True, help="Target domain (tech, healthcare, legal, trades, finance)")
    parser.add_argument("--id", required=True, help="Unique resource slug id")
    parser.add_argument("--title", required=True, help="Canonical title")
    parser.add_argument("--url", required=True, help="Verified active URL")
    parser.add_argument("--platform", required=True, help="Platform name (e.g. YouTube, Coursera, Docs)")
    parser.add_argument("--type", default="course", choices=["course", "youtube_video", "certification", "documentation"])
    parser.add_argument("--skills", required=True, help="Comma-separated skills covered")
    parser.add_argument("--difficulty", default="beginner", choices=["beginner", "intermediate", "advanced"])
    parser.add_argument("--duration", type=float, default=5.0, help="Estimated duration in hours")
    parser.add_argument("--free", action="store_true", default=True, help="Is freely accessible")
    parser.add_argument("--desc", required=True, help="Description for semantic search")
    parser.add_argument("--bypass-probe", action="store_true", help="Bypass live HTTP network probe")

    args = parser.parse_args()
    skills_list = [s.strip() for s in args.skills.split(",") if s.strip()]

    try:
        add_resource_to_catalog(
            domain=args.domain,
            resource_id=args.id,
            title=args.title,
            url=args.url,
            platform=args.platform,
            resource_type=args.type,
            skills_covered=skills_list,
            difficulty=args.difficulty,
            duration_hours=args.duration,
            is_free=args.free,
            description=args.desc,
            bypass_probe=args.bypass_probe
        )
    except Exception as err:
        print(f"Failed to ingest resource: {err}")
        sys.exit(1)

