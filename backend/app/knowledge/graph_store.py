"""Skill Dependency Knowledge Graph (GraphRAG DAG Engine).

Builds an in-memory Directed Acyclic Graph (DAG) of technical and domain skills,
validates graph acyclicity, performs multi-hop prerequisite traversal,
and returns pedagogically sequenced learning paths tailored to candidate known skills.
"""
import os
import json
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict, deque
from app.knowledge.models import SkillNode, PrerequisiteChainResult
from app.utils.logger import logger

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "catalog", "skill_graph_catalog.json")

class SkillDependencyGraph:
    """Manages the directed acyclic graph of skill competencies and prerequisites."""

    def __init__(self, catalog_path: Optional[str] = None):
        self.catalog_path = catalog_path or CATALOG_PATH
        self.nodes: Dict[str, SkillNode] = {}
        # Forward edges: prerequisite -> dependents (skills unlocked)
        self.dependents: Dict[str, Set[str]] = defaultdict(set)
        # Backward edges: skill -> required prerequisites
        self.prerequisites: Dict[str, Set[str]] = defaultdict(set)
        self._is_loaded = False
        self.load_graph()

    def load_graph(self) -> int:
        """Load skill nodes and construct directed edges with cycle verification."""
        if not os.path.exists(self.catalog_path):
            logger.warning(f"Skill graph catalog not found at {self.catalog_path}")
            return 0

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.nodes.clear()
            self.dependents.clear()
            self.prerequisites.clear()

            for item in data:
                node = SkillNode(**item)
                node_id = node.id.strip().lower()
                self.nodes[node_id] = node

            # Construct directed edges
            for node_id, node in self.nodes.items():
                for prereq_id in node.prerequisites:
                    prereq_clean = prereq_id.strip().lower()
                    if prereq_clean in self.nodes:
                        self.prerequisites[node_id].add(prereq_clean)
                        self.dependents[prereq_clean].add(node_id)
                    else:
                        logger.debug(f"Prerequisite '{prereq_clean}' referenced by '{node_id}' not found in graph catalog.")

            # Validate acyclicity
            if not self._validate_acyclic():
                raise ValueError("Skill dependency graph contains a cyclic dependency loop!")

            self._is_loaded = True
            logger.info(f"Loaded Skill Dependency Graph: {len(self.nodes)} nodes, {sum(len(v) for v in self.prerequisites.values())} prerequisite edges.")
            return len(self.nodes)

        except Exception as e:
            logger.error(f"Failed to load skill graph: {e}")
            return 0

    def _validate_acyclic(self) -> bool:
        """Check for cycles using Kahn's algorithm (topological sort test)."""
        in_degree = {node: len(self.prerequisites[node]) for node in self.nodes}
        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        visited_count = 0

        while queue:
            curr = queue.popleft()
            visited_count += 1
            for dependent in self.dependents[curr]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        return visited_count == len(self.nodes)

    def find_node(self, skill_name: str) -> Optional[SkillNode]:
        """Find a skill node by exact id or fuzzy substring match."""
        if not skill_name:
            return None
        clean = skill_name.strip().lower().replace(" ", "_").replace("-", "_")
        if clean in self.nodes:
            return self.nodes[clean]

        # Substring / alias search
        for node_id, node in self.nodes.items():
            if node_id in clean or clean in node_id or skill_name.strip().lower() in node.name.lower():
                return node
        return None

    def get_prerequisite_closure(self, target_node_id: str) -> List[str]:
        """
        Traverse backward to compute the complete transitive closure of prerequisites.
        Returns prerequisites topologically sorted (earliest foundational skills first).
        """
        target_clean = target_node_id.strip().lower()
        if target_clean not in self.nodes:
            return []

        # Reachability via BFS/DFS
        visited: Set[str] = set()
        stack = [target_clean]
        subgraph_nodes: Set[str] = set()

        while stack:
            curr = stack.pop()
            if curr not in visited:
                visited.add(curr)
                subgraph_nodes.add(curr)
                for prereq in self.prerequisites[curr]:
                    stack.append(prereq)

        # Topological sort of subgraph using in-degrees
        in_degree = {node: 0 for node in subgraph_nodes}
        for node in subgraph_nodes:
            for prereq in self.prerequisites[node]:
                if prereq in subgraph_nodes:
                    in_degree[node] += 1

        queue = deque([node for node in subgraph_nodes if in_degree[node] == 0])
        ordered: List[str] = []

        while queue:
            curr = queue.popleft()
            ordered.append(curr)
            for dependent in self.dependents[curr]:
                if dependent in subgraph_nodes:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return ordered

    def resolve_prerequisites(
        self,
        target_skills: List[str],
        candidate_known_skills: List[str]
    ) -> List[SkillNode]:
        """
        Given target skill gaps and candidate known skills:
        1. Identifies missing prerequisite ancestors.
        2. Filters out skills the candidate already possesses.
        3. Returns unfulfilled skills in strict pedagogical sequence (fundamentals first).
        """
        known_set = {s.strip().lower().replace(" ", "_").replace("-", "_") for s in candidate_known_skills}
        ordered_skill_ids: List[str] = []
        seen_resolved: Set[str] = set()

        for target in target_skills:
            target_node = self.find_node(target)
            if not target_node:
                continue

            chain = self.get_prerequisite_closure(target_node.id)
            for skill_id in chain:
                if skill_id not in seen_resolved:
                    seen_resolved.add(skill_id)
                    # Check if candidate already knows this prerequisite
                    is_known = any(
                        skill_id in k or k in skill_id or 
                        self.nodes[skill_id].name.lower() in k.replace("_", " ") or 
                        k.replace("_", " ") in self.nodes[skill_id].name.lower()
                        for k in known_set
                    )
                    if not is_known:
                        ordered_skill_ids.append(skill_id)

        return [self.nodes[sid] for sid in ordered_skill_ids if sid in self.nodes]

_GRAPH_SINGLETON: Optional[SkillDependencyGraph] = None

def get_skill_graph() -> SkillDependencyGraph:
    """Singleton getter for SkillDependencyGraph."""
    global _GRAPH_SINGLETON
    if _GRAPH_SINGLETON is None:
        _GRAPH_SINGLETON = SkillDependencyGraph()
    return _GRAPH_SINGLETON

