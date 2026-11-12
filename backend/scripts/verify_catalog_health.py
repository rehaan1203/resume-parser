"""Resource Verification & Health-Check Automation (Option 4).

Asynchronously probes all URLs across multi-domain catalogs, verifies HTTP status codes,
measures latency, updates catalog metadata, and writes an executive health report.
"""
import os
import sys
import json
import asyncio
import time
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone
import httpx

CATALOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "knowledge", "catalog")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "knowledge", "reports")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Semaphore to prevent rate limiting or connection exhaustion
CONCURRENCY_LIMIT = 5
TIMEOUT_SECONDS = 10.0


async def check_url_health(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, url: str) -> Dict[str, Any]:
    """Probe a single URL using HEAD followed by GET fallback."""
    headers = {"User-Agent": USER_AGENT}
    async with semaphore:
        start_time = time.time()
        try:
            # 1. Attempt lightweight HEAD request
            response = await client.head(url, headers=headers, follow_redirects=True, timeout=TIMEOUT_SECONDS)
            latency_ms = round((time.time() - start_time) * 1000, 1)

            # If HEAD is rejected by server (403, 405) or suspicious, try a shallow GET
            if response.status_code in (403, 405):
                start_get = time.time()
                response = await client.get(url, headers=headers, follow_redirects=True, timeout=TIMEOUT_SECONDS)
                latency_ms = round((time.time() - start_get) * 1000, 1)

            status_code = response.status_code
            if 200 <= status_code < 400:
                health = "active"
            elif status_code in (403, 429):
                health = "degraded"  # Access restricted/rate limited, but server exists
            else:
                health = "broken"

            return {
                "url": url,
                "status_code": status_code,
                "health_status": health,
                "latency_ms": latency_ms,
                "error": None
            }
        except httpx.TimeoutException:
            return {
                "url": url,
                "status_code": 408,
                "health_status": "degraded",
                "latency_ms": TIMEOUT_SECONDS * 1000,
                "error": "Request timeout"
            }
        except Exception as e:
            return {
                "url": url,
                "status_code": 0,
                "health_status": "broken",
                "latency_ms": 0.0,
                "error": str(e)
            }


async def audit_all_catalogs(update_files: bool = True) -> Dict[str, Any]:
    """Audit all catalog JSON files in the catalog directory."""
    if not os.path.exists(CATALOG_DIR):
        print(f"Catalog directory not found: {CATALOG_DIR}")
        return {}

    os.makedirs(REPORTS_DIR, exist_ok=True)
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    all_resources: List[Tuple[str, Dict[str, Any]]] = []

    # Collect all catalog items
    catalog_files = [f for f in os.listdir(CATALOG_DIR) if f.endswith("_catalog.json") and not f.startswith("taxonomy") and not f.startswith("phrasing")]

    for filename in catalog_files:
        filepath = os.path.join(CATALOG_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            items = json.load(f)
            for item in items:
                all_resources.append((filename, item))

    print(f"Checking health for {len(all_resources)} resources across {len(catalog_files)} catalogs...")

    async with httpx.AsyncClient(verify=False) as client:
        tasks = [
            check_url_health(client, semaphore, item["url"])
            for _, item in all_resources
        ]
        results = await asyncio.gather(*tasks)

    # Aggregate metrics
    now_iso = datetime.now(timezone.utc).isoformat()
    now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    healthy_count = 0
    degraded_count = 0
    broken_count = 0
    total_latency = 0.0
    detailed_results = []

    url_to_result = {r["url"]: r for r in results}

    for filename, item in all_resources:
        res = url_to_result.get(item["url"], {"health_status": "broken", "latency_ms": 0.0, "status_code": 0})
        status = res["health_status"]
        if status == "active":
            healthy_count += 1
            item["verified_at"] = now_date
        elif status == "degraded":
            degraded_count += 1
        else:
            broken_count += 1

        item["health_status"] = status
        item["last_checked_at"] = now_iso
        total_latency += res.get("latency_ms", 0.0)

        detailed_results.append({
            "id": item.get("id"),
            "title": item.get("title"),
            "url": item.get("url"),
            "catalog": filename,
            "status_code": res.get("status_code"),
            "health_status": status,
            "latency_ms": res.get("latency_ms"),
            "error": res.get("error")
        })

    # Update catalog JSON files if requested
    if update_files:
        catalog_to_items: Dict[str, List[Dict[str, Any]]] = {}
        for filename, item in all_resources:
            catalog_to_items.setdefault(filename, []).append(item)

        for filename, items in catalog_to_items.items():
            filepath = os.path.join(CATALOG_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)

    total = len(all_resources)
    health_pct = round((healthy_count / total * 100), 1) if total > 0 else 0.0
    avg_latency = round((total_latency / total), 1) if total > 0 else 0.0

    report = {
        "timestamp": now_iso,
        "total_resources": total,
        "healthy": healthy_count,
        "degraded": degraded_count,
        "broken": broken_count,
        "health_percentage": health_pct,
        "average_latency_ms": avg_latency,
        "resources": detailed_results
    }

    report_path = os.path.join(REPORTS_DIR, "health_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n============================================================")
    print("Catalog Health Check Summary:")
    print("============================================================")
    print(f"Total Resources: {total}")
    print(f"Healthy (Active): {healthy_count} ({health_pct}%)")
    print(f"Degraded: {degraded_count}")
    print(f"Broken: {broken_count}")
    print(f"Average Latency: {avg_latency}ms")
    print(f"Report written to: {report_path}")
    print("============================================================\n")

    return report


if __name__ == "__main__":
    asyncio.run(audit_all_catalogs(update_files=True))

