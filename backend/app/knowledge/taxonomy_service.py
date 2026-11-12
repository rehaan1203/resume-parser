"""Taxonomy Normalization Service (Option 3).

Maps diverse industry jargon, statutory citations, and synonyms to canonical competencies
prior to score calculation.
"""
import os
import json
import re
from typing import List, Dict, Optional
from app.utils.logger import logger

TAXONOMY_PATH = os.path.join(os.path.dirname(__file__), "catalog", "taxonomy_catalog.json")

class TaxonomyService:
    def __init__(self):
        self._synonym_map: Dict[str, str] = {}
        self._canonical_list: List[str] = []
        self._is_loaded = False
        self._load_taxonomy()

    def _load_taxonomy(self):
        if self._is_loaded or not os.path.exists(TAXONOMY_PATH):
            return
        try:
            with open(TAXONOMY_PATH, "r", encoding="utf-8") as f:
                entries = json.load(f)
            for item in entries:
                canon = item.get("canonical", "").strip().lower()
                if not canon:
                    continue
                self._canonical_list.append(canon)
                self._synonym_map[canon] = canon
                for alias in item.get("aliases", []):
                    alias_clean = alias.strip().lower()
                    if alias_clean:
                        self._synonym_map[alias_clean] = canon
            self._is_loaded = True
            logger.info(f"Loaded {len(self._synonym_map)} taxonomy synonym mappings.")
        except Exception as e:
            logger.error(f"Failed to load taxonomy catalog: {e}")

    def normalize_term(self, term: str) -> str:
        """Map a skill or requirement phrase to its canonical form if known."""
        if not term:
            return ""
        clean = term.strip().lower()
        # Direct dictionary match
        if clean in self._synonym_map:
            return self._synonym_map[clean]
        
        # Substring / boundary match for known citations (e.g. '45 cfr part 164')
        for alias, canonical in self._synonym_map.items():
            if len(alias) >= 4 and alias in clean:
                return canonical

        return clean

    def normalize_skills(self, skills: List[str]) -> List[str]:
        """Normalize a list of extracted skills/requirements, deduplicating canon names."""
        normalized = set()
        for s in skills:
            norm = self.normalize_term(s)
            normalized.add(norm)
        return sorted(list(normalized))


_global_taxonomy: Optional[TaxonomyService] = None

def get_taxonomy_service() -> TaxonomyService:
    global _global_taxonomy
    if _global_taxonomy is None:
        _global_taxonomy = TaxonomyService()
    return _global_taxonomy

