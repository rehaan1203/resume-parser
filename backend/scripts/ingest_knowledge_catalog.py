"""Offline CLI script to validate URLs and ingest catalogs into the RAG Knowledge Base."""
import asyncio
import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.knowledge.retriever import KnowledgeRetriever
from app.utils.logger import logger

async def main():
    print("=" * 60)
    print("Ingesting and Indexing Multi-Domain RAG Catalogs...")
    print("=" * 60)

    retriever = KnowledgeRetriever()
    count = await retriever.initialize_and_index_catalogs()

    print(f"\nSuccessfully verified and indexed {count} resources across Tech, Healthcare, Trades, and Legal.")

    # Run quick test queries
    print("\nRunning smoke verification queries:")
    test_skills = [
        ("Docker", "tech"),
        ("BLS", "healthcare"),
        ("EPA 608", "trades"),
        ("Contract Drafting", "legal")
    ]
    for skill, domain in test_skills:
        res = await retriever.retrieve_for_skill(skill, domain=domain, top_k=1)
        if res:
            top = res[0].resource
            print(f"  [{domain.upper()}] '{skill}' -> '{top.title}' ({top.platform}) | URL: {top.url}")
        else:
            print(f"  [{domain.upper()}] '{skill}' -> No match found")

    print("\nCatalog Ingestion Complete.")

if __name__ == "__main__":
    asyncio.run(main())

