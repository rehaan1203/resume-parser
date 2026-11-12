"""Hybrid Knowledge Retriever for RAG Knowledge Base (Stage 2)."""
import os
import json
import re
from typing import List, Dict, Any, Optional, Set
from app.knowledge.models import VerifiedResource, ResourceSearchResult, ResourceType, PhrasingTemplate, TransitionBridge, InterviewGuideItem, DiagramResource, QueryConstraints
from app.knowledge.embedding_service import EmbeddingService
from app.knowledge.vector_store import BaseVectorStore, get_vector_store
from app.knowledge.bm25_scorer import get_bm25_index, ReciprocalRankFusion
from app.knowledge.geo_router import get_geo_router
from app.knowledge.semantic_cache import get_semantic_cache
from app.knowledge.cdc_bus import get_cdc_bus, CDCEvent
from app.knowledge.ragas_evaluator import get_ragas_evaluator
from app.config import settings
from app.utils.logger import logger

CATALOG_DIR = os.path.join(os.path.dirname(__file__), "catalog")

class KnowledgeRetriever:
    """Retrieves verified learning resources matching candidate skill gaps."""

    def __init__(self, vector_store: Optional[BaseVectorStore] = None, embedding_service: Optional[EmbeddingService] = None):
        self.vector_store = vector_store or get_vector_store()
        self.embedding_service = embedding_service or EmbeddingService()
        self._is_indexed = False
        self._parent_doc_map: Dict[str, VerifiedResource] = {}
        self._transition_bridges: Dict[Tuple[str, str], TransitionBridge] = {}
        self._interview_guides: List[InterviewGuideItem] = []
        self._phrasing_templates: List[PhrasingTemplate] = []
        self._diagram_catalog: List[DiagramResource] = []

    async def initialize_and_index_catalogs(self) -> int:
        """Load all JSON catalogs and index them into the vector store, BM25 index, and in-memory caches."""
        if self._is_indexed:
            return await self.vector_store.count()

        if not os.path.exists(CATALOG_DIR):
            logger.warning(f"Catalog directory not found at {CATALOG_DIR}")
            return 0

        # 1. Load in-memory specialized catalogs (zero disk I/O at runtime)
        self._load_specialized_catalogs()

        # 2. Gather verified resources for parallel batch embedding
        resources_to_index: List[VerifiedResource] = []
        texts_to_embed: List[str] = []

        for filename in os.listdir(CATALOG_DIR):
            if filename.endswith(".json"):
                # Skip non-resource catalogs with dedicated domain models
                if any(x in filename for x in ["interview", "phrasing", "taxonomy", "transition_bridge", "skill_graph", "graph", "diagram"]):
                    continue
                filepath = os.path.join(CATALOG_DIR, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for item in data:
                        res = VerifiedResource(**item)
                        resources_to_index.append(res)
                        texts_to_embed.append(f"{res.title} {res.description} {' '.join(res.skills_covered)}")
                except Exception as e:
                    logger.error(f"Error loading catalog file {filename}: {e}")

        # Store parent map for hierarchical small-to-big resolution
        self._parent_doc_map = {res.id: res for res in resources_to_index}

        # 3. Parallel batch embedding into vector store
        if texts_to_embed:
            vectors = await self.embedding_service.embed_documents(texts_to_embed)
            for res, vec in zip(resources_to_index, vectors):
                await self.vector_store.upsert(res, vec)

        # 4. Index resources into sparse BM25 index
        bm25 = get_bm25_index()
        bm25.index_resources(resources_to_index)

        # 5. Register with CDC Event Bus for live zero-downtime updates
        cdc_bus = get_cdc_bus()
        cdc_bus.subscribe("RESOURCE_CREATED", self._on_cdc_resource_update)
        cdc_bus.subscribe("RESOURCE_UPDATED", self._on_cdc_resource_update)

        self._is_indexed = True
        count = len(resources_to_index)
        logger.info(f"RAG Knowledge Base initialized with {count} verified resources, BM25 index, and CDC event bus.")
        return count

    async def _on_cdc_resource_update(self, event: CDCEvent):
        """Handle hot-reload CDC event for incremental vector and BM25 index updates."""
        if event.payload:
            try:
                res = VerifiedResource(**event.payload)
                self._parent_doc_map[res.id] = res
                text = f"{res.title} {res.description} {' '.join(res.skills_covered)}"
                vec = await self.embedding_service.embed_documents([text])
                if vec:
                    await self.vector_store.upsert(res, vec[0])
                get_bm25_index().index_resources(list(self._parent_doc_map.values()))
                logger.info(f"KnowledgeRetriever CDC: live-updated resource '{res.id}'")
            except Exception as e:
                logger.error(f"Error handling CDC event in KnowledgeRetriever: {e}")

    def _load_specialized_catalogs(self):
        """Load specialized catalogs into memory once for lightning-fast lookups."""
        try:
            # Transition bridges
            bridge_path = os.path.join(CATALOG_DIR, "transition_bridge_catalog.json")
            if os.path.exists(bridge_path) and not self._transition_bridges:
                with open(bridge_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    src = item.get("source_domain", "").strip().lower()
                    tgt = item.get("target_domain", "").strip().lower()
                    self._transition_bridges[(src, tgt)] = TransitionBridge(**item)

            # Phrasing templates
            phrasing_path = os.path.join(CATALOG_DIR, "phrasing_catalog.json")
            if os.path.exists(phrasing_path) and not self._phrasing_templates:
                with open(phrasing_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._phrasing_templates = [PhrasingTemplate(**item) for item in data]

            # Interview guides
            interview_path = os.path.join(CATALOG_DIR, "interview_catalog.json")
            if os.path.exists(interview_path) and not self._interview_guides:
                with open(interview_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._interview_guides = [InterviewGuideItem(**item) for item in data]

            # Diagram catalog (Mermaid Architecture Visuals)
            diagram_path = os.path.join(CATALOG_DIR, "diagram_catalog.json")
            if os.path.exists(diagram_path) and not self._diagram_catalog:
                with open(diagram_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._diagram_catalog = [DiagramResource(**item) for item in data]
        except Exception as e:
            logger.error(f"Error caching specialized catalogs: {e}")

    def get_diagrams_for_skills(
        self,
        skills: List[str],
        domain: Optional[str] = None,
        limit: int = 2
    ) -> List[DiagramResource]:
        """Retrieve verified architecture diagrams matching candidate skill gaps."""
        if not self._diagram_catalog:
            self._load_specialized_catalogs()

        clean_skills = [s.strip().lower() for s in skills]
        target_domain = (domain or "").lower()

        matched = []
        for diag in self._diagram_catalog:
            score = 0
            if target_domain and diag.domain.lower() == target_domain:
                score += 1
            overlap = sum(1 for s in diag.associated_skills if any(cs in s.lower() or s.lower() in cs for cs in clean_skills))
            if overlap > 0:
                score += overlap * 2
                matched.append((score, diag))

        matched.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in matched[:limit]]

    async def retrieve_for_skill(
        self,
        skill: str,
        domain: str = "tech",
        top_k: int = 2,
        seniority: str = "mid",
        is_career_transition: bool = False,
        constraints: Optional[QueryConstraints] = None,
        preferred_vendors: Optional[Set[str]] = None,
    ) -> List[ResourceSearchResult]:
        """Hybrid search combining dense vector cosine similarity and exact tag matching with contextual reranking."""
        if not self._is_indexed:
            await self.initialize_and_index_catalogs()

        try:
            skill_clean = skill.strip().lower()

            # 1. Geo-Router: detect or read target jurisdiction
            from app.knowledge.geo_router import get_geo_router
            geo_router = get_geo_router()
            target_jur = (constraints.target_jurisdiction if constraints else None) or geo_router.detect_jurisdiction(skill)

            # Domain strictness: normalize aliases (including domain_detector labels) to catalog keys
            alias_map = {
                "technology": "tech", "software": "tech", "it": "tech",
                "software_engineering": "tech", "data_science": "tech",
                "product": "tech", "engineering": "tech", "ai": "tech",
                "health": "healthcare", "medical": "healthcare", "nursing": "healthcare",
                "law": "legal", "trade": "trades", "skilled_trades": "trades",
                "financial": "finance", "accounting": "finance",
                "human_resources": "hr",
            }
            clean_dom = (domain or "").strip().lower()
            resolved_dom = alias_map.get(clean_dom, clean_dom)
            domain_filter = None if resolved_dom in ("unknown", "", None) else resolved_dom

            # 2. HyDE Query Expansion (Hypothetical Document Embeddings)
            query_text = skill_clean
            if getattr(settings, "rag_enable_hyde", True):
                try:
                    from app.knowledge.hyde_expander import get_hyde_expander
                    expander = get_hyde_expander()
                    hyde_obj = await expander.expand(skill_clean, domain=domain)
                    query_text = f"{skill_clean} {hyde_obj.hypothetical_curriculum}"
                except Exception as hyde_err:
                    logger.debug(f"HyDE expansion skipped: {hyde_err}")

            query_vector = await self.embedding_service.embed_query(query_text)

            # 3. Semantic Vector Cache Check (Sub-millisecond retrieval)
            from app.knowledge.crag_evaluator import CRAGEvaluator
            effective_vendors = CRAGEvaluator.extract_vendors(skill_clean) or (preferred_vendors or set())
            sen_norm = (seniority or "mid").strip().lower()
            sen_bucket = "junior" if sen_norm in ("entry", "fresher", "junior") else ("senior" if sen_norm in ("senior", "lead") else "mid")
            vendor_tag = ",".join(sorted(effective_vendors)) if effective_vendors else "ANY"
            vendor_scope = f"{vendor_tag}|{sen_bucket}"
            from app.knowledge.semantic_cache import get_semantic_cache
            semantic_cache = get_semantic_cache()
            cached_hits = semantic_cache.get(
                query_vector,
                domain=resolved_dom,
                jurisdiction=target_jur,
                vendor_scope=vendor_scope,
            )
            if cached_hits:
                logger.debug(f"KnowledgeRetriever: instant semantic cache hit for '{skill}'")
                return cached_hits[:top_k]

            # 4. Dense Vector Search
            raw_results = await self.vector_store.search(
                query_vector=query_vector,
                domain=domain_filter,
                top_k=top_k * 4
            )

            # 5. Sparse BM25 Search
            from app.knowledge.bm25_scorer import get_bm25_index, ReciprocalRankFusion
            bm25 = get_bm25_index()
            sparse_results = bm25.search(query=query_text, domain=domain_filter, top_k=top_k * 4)

            # 6. Reciprocal Rank Fusion (RRF: Dense + BM25)
            rrf = ReciprocalRankFusion(k=60, weight_dense=0.60, weight_sparse=0.40)
            fused_candidates = rrf.fuse(dense_results=raw_results, sparse_results=sparse_results, top_k=top_k * 6)

            # Cross-domain fallback if strict domain filter yielded no hits
            if not fused_candidates and domain_filter is not None:
                raw_fallback = await self.vector_store.search(query_vector=query_vector, domain=None, top_k=top_k * 4)
                sparse_fallback = bm25.search(query=query_text, domain=None, top_k=top_k * 4)
                fused_candidates = rrf.fuse(dense_results=raw_fallback, sparse_results=sparse_fallback, top_k=top_k * 6)

            scored_results: List[ResourceSearchResult] = []
            from app.api.routes.telemetry import IN_MEMORY_CLICK_COUNTS
            from app.knowledge.self_query import get_self_query_synthesizer
            from app.knowledge.recency_scorer import get_recency_scorer

            active_constraints = constraints or get_self_query_synthesizer().synthesize_constraints(skill)
            recency_scorer = get_recency_scorer()

            for item in fused_candidates:
                resource = item.resource

                # Hierarchical Small-to-Big: resolve child chunk to full parent document
                if getattr(resource, "parent_id", None) and resource.parent_id in self._parent_doc_map:
                    resource = self._parent_doc_map[resource.parent_id]

                # Self-querying hard constraint & negative anti-skill filter check
                if active_constraints and not get_self_query_synthesizer().matches_constraints(resource, active_constraints):
                    continue

                # Geo-Router compatibility check & strict regulatory territorial pruning
                geo_mult = geo_router.score_geo_compatibility(
                    getattr(resource, "jurisdiction", "GLOBAL"),
                    target_jurisdiction=target_jur,
                    domain=resolved_dom
                )
                if geo_mult <= 0.0:
                    continue

                # Target domain bonus & strictness check
                domain_match_bonus = 0.2 if (domain_filter and resource.domain.lower() == domain_filter) else 0.0
                tag_match = 1.0 if any(s.lower() in skill_clean or skill_clean in s.lower() for s in resource.skills_covered) else (0.5 if (skill_clean in resource.description.lower() or skill_clean in resource.title.lower()) else 0.0)

                # Candidate engagement / popularity bonus from click telemetry
                clicks = IN_MEMORY_CLICK_COUNTS.get(resource.id, 0)
                pop_bonus = min(0.05, (clicks / 50.0) * 0.05)

                raw_score = 0.50 * item.score + 0.35 * tag_match + 0.10 * (1.0 if domain_match_bonus > 0 else 0.0) + pop_bonus

                # Recency-aware time-decay scoring
                recency_mult = recency_scorer.calculate_recency_multiplier(resource)
                hybrid_score = round(raw_score * recency_mult * geo_mult, 4)

                # Temporal Video Chapter Deep-Linking
                if getattr(resource, "chapters", None):
                    for ch in resource.chapters:
                        ch_title = ch.title.lower()
                        if any(term in ch_title for term in skill_clean.split() if len(term) > 2) or skill_clean in ch_title:
                            base_url = str(resource.url)
                            sep = "&" if "?" in base_url else "?"
                            resource.active_timestamp_url = f"{base_url}{sep}{ch.url_anchor}"
                            resource.matched_chapter = ch.title
                            break

                matched = [s for s in resource.skills_covered if s.lower() in skill_clean or skill_clean in s.lower()]
                scored_results.append(ResourceSearchResult(
                    resource=resource,
                    score=min(1.0, hybrid_score),
                    matched_skills=matched
                ))

            # Deduplicate by resource id
            dedup_dict = {}
            for sr in scored_results:
                if sr.resource.id not in dedup_dict or sr.score > dedup_dict[sr.resource.id].score:
                    dedup_dict[sr.resource.id] = sr
            scored_results = list(dedup_dict.values())
            scored_results.sort(key=lambda x: x.score, reverse=True)

            # Enforce strict cloud vendor affinity before any threshold/fallback selection
            scored_results = [
                sr for sr in scored_results
                if not CRAGEvaluator._detect_vendor_conflict(skill_clean, sr.resource, preferred_vendors=effective_vendors or None)
            ]

            # Apply similarity threshold cutoff to prevent irrelevant resource leakage
            min_threshold = float(getattr(settings, "rag_similarity_threshold", 0.35))
            filtered = [r for r in scored_results if r.score >= min_threshold]

            # Corrective RAG (CRAG) Evaluator
            certified_candidates = filtered
            if getattr(settings, "rag_enable_crag", True) and filtered:
                try:
                    from app.knowledge.crag_evaluator import get_crag_evaluator
                    crag = get_crag_evaluator()
                    certified, grades, needs_fallback = crag.filter_and_evaluate(
                        candidates=filtered,
                        query_skill=skill_clean,
                        seniority=seniority,
                        domain=resolved_dom,
                        preferred_vendors=effective_vendors or None,
                    )
                    if certified:
                        certified_candidates = certified
                except Exception as crag_err:
                    logger.debug(f"CRAG evaluation skipped: {crag_err}")

            # Context-Aware Cross-Encoder Reranker
            from app.knowledge.reranker import get_reranker
            reranker = get_reranker()

            final_results = []
            if certified_candidates:
                final_results = reranker.rerank(
                    query=skill,
                    candidates=certified_candidates,
                    seniority=seniority,
                    is_career_transition=is_career_transition,
                    top_k=top_k
                )
            else:
                # Fall back to top non-conflicting evidence candidates if similarity threshold was too strict
                evidence_candidates = [r for r in scored_results if r.score >= 0.2]
                if evidence_candidates:
                    final_results = reranker.rerank(
                        query=skill,
                        candidates=evidence_candidates,
                        seniority=seniority,
                        is_career_transition=is_career_transition,
                        top_k=top_k
                    )

            # 7. RAGAS Triad Hallucination Evaluation
            if final_results:
                try:
                    from app.knowledge.ragas_evaluator import get_ragas_evaluator
                    ragas = get_ragas_evaluator()
                    ragas.evaluate_triad(
                        query_skills=[skill_clean],
                        retrieved_resources=[r.resource for r in final_results],
                        target_domain=resolved_dom,
                        seniority=seniority
                    )
                except Exception as ragas_err:
                    logger.debug(f"RAGAS Triad evaluation notice: {ragas_err}")

                # 8. Store in Semantic Vector Cache
                semantic_cache.set(
                    query_text=skill,
                    query_vector=query_vector,
                    results=final_results,
                    domain=resolved_dom,
                    jurisdiction=target_jur,
                    vendor_scope=vendor_scope,
                )

            return final_results

        except Exception as e:
            logger.error(f"Knowledge retrieval error for skill {skill}: {e}")
            return []

    async def retrieve_for_skill_gaps(
        self,
        skill_gaps: List[str],
        domain: str = "tech",
        max_resources_per_gap: int = 2,
        seniority: str = "mid",
        is_career_transition: bool = False,
        known_skills: Optional[List[str]] = None,
        constraints: Optional[QueryConstraints] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Retrieve verified resources grouped by each skill gap with Graph sequencing & seniority weighting."""
        gaps_to_query = list(skill_gaps)
        if getattr(settings, "rag_enable_graph", True):
            try:
                from app.knowledge.graph_store import get_skill_graph
                graph = get_skill_graph()
                unfulfilled_nodes = graph.resolve_prerequisites(skill_gaps, known_skills or [])
                if unfulfilled_nodes:
                    gaps_to_query = [n.id.replace("_", " ") for n in unfulfilled_nodes]
            except Exception as graph_err:
                logger.debug(f"Graph prerequisite expansion skipped: {graph_err}")

        out = {}
        for gap in gaps_to_query[:5]:
            results = await self.retrieve_for_skill(
                gap,
                domain=domain,
                top_k=max_resources_per_gap,
                seniority=seniority,
                is_career_transition=is_career_transition,
                constraints=constraints
            )
            out[gap] = [r.resource.model_dump() for r in results]
        return out

    async def search_for_gaps(
        self,
        skills: List[str],
        domain: Optional[str] = None,
        limit: int = 6,
        seniority: str = "mid",
        is_career_transition: bool = False,
        known_skills: Optional[List[str]] = None,
        constraints: Optional[QueryConstraints] = None,
        context_text: Optional[str] = None,
    ) -> List[VerifiedResource]:
        """Flattened search returning top unique verified resources for a list of skills with GraphRAG ordering."""
        if not self._is_indexed:
            await self.initialize_and_index_catalogs()

        from app.knowledge.crag_evaluator import CRAGEvaluator
        batch_vendor_hint = " ".join(list(skills) + ([context_text] if context_text else []))
        batch_vendors = CRAGEvaluator.extract_vendors(batch_vendor_hint)

        # 1. Prerequisite GraphRAG Expansion & Sequencing
        skills_to_query = list(skills)
        if getattr(settings, "rag_enable_graph", True):
            try:
                from app.knowledge.graph_store import get_skill_graph
                graph = get_skill_graph()
                unfulfilled_nodes = graph.resolve_prerequisites(skills, known_skills or [])
                if unfulfilled_nodes:
                    skills_to_query = [n.id.replace("_", " ") for n in unfulfilled_nodes]
            except Exception as graph_err:
                logger.debug(f"Graph prerequisite expansion skipped: {graph_err}")

        seen_urls = set()
        collected: List[VerifiedResource] = []
        
        for skill in skills_to_query[:8]:
            results = await self.retrieve_for_skill(
                skill=skill,
                domain=domain or "unknown",
                top_k=2,
                seniority=seniority,
                is_career_transition=is_career_transition,
                constraints=constraints,
                preferred_vendors=batch_vendors or None,
            )
            for res_wrapper in results:
                res = getattr(res_wrapper, "resource", res_wrapper)
                if res.url not in seen_urls:
                    seen_urls.add(res.url)
                    collected.append(res)
                    if len(collected) >= limit:
                        return collected
        return collected

    async def get_phrasing_templates_for_gaps(
        self,
        skills: List[str],
        domain: Optional[str] = None,
        limit: int = 4
    ) -> List[PhrasingTemplate]:
        """Retrieve curated STAR phrasing templates matching candidate skill gaps (in-memory cached)."""
        if not self._phrasing_templates:
            self._load_specialized_catalogs()
        templates = self._phrasing_templates

        matched = []
        clean_skills = [s.strip().lower() for s in skills]
        target_domain = (domain or "").lower()

        # Score templates by skill and domain match
        for tmpl in templates:
            score = 0
            if target_domain and tmpl.domain == target_domain:
                score += 2
            for s in tmpl.skills:
                if any(s in cs or cs in s for cs in clean_skills):
                    score += 3
            if score > 0:
                matched.append((tmpl, score))

        matched.sort(key=lambda x: x[1], reverse=True)
        return [t[0] for t in matched[:limit]]

    def get_transition_bridge(
        self,
        source_domain: str,
        target_domain: str
    ) -> Optional[TransitionBridge]:
        """Retrieve curated transition bridge advice and certifications between two domains (O(1) in-memory)."""
        if not self._transition_bridges:
            self._load_specialized_catalogs()

        # Domain alias normalization
        alias_map = {
            "technology": "tech",
            "software": "tech",
            "it": "tech",
            "health": "healthcare",
            "medical": "healthcare",
            "nursing": "healthcare",
            "law": "legal",
            "trade": "trades",
            "skilled_trades": "trades",
            "financial": "finance",
            "accounting": "finance"
        }

        src_raw = (source_domain or "").strip().lower()
        tgt_raw = (target_domain or "").strip().lower()

        src = alias_map.get(src_raw, src_raw)
        tgt = alias_map.get(tgt_raw, tgt_raw)

        return self._transition_bridges.get((src, tgt))

    def get_interview_guides_for_skills(
        self,
        skills: List[str],
        domain: Optional[str] = None,
        limit: int = 3
    ) -> List[InterviewGuideItem]:
        """Retrieve interview questions, evaluation rubrics, and STAR answers matching candidate skills (in-memory)."""
        if not self._interview_guides:
            self._load_specialized_catalogs()
        items = self._interview_guides

        matched = []
        clean_skills = [s.strip().lower() for s in skills]
        target_domain = (domain or "").lower()

        for guide in items:
            score = 0
            if target_domain and guide.domain == target_domain:
                score += 2
            focus = guide.skill_focus.lower()
            if any(focus in cs or cs in focus for cs in clean_skills):
                score += 4
            if score > 0:
                matched.append((guide, score))

        matched.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matched[:limit]]


_global_retriever: Optional[KnowledgeRetriever] = None

def get_retriever() -> KnowledgeRetriever:
    """Singleton getter for the shared KnowledgeRetriever."""
    global _global_retriever
    if _global_retriever is None:
        _global_retriever = KnowledgeRetriever()
    return _global_retriever

