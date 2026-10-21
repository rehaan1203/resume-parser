# Modular Prompts Architecture (`app.prompts`)

This package houses all prompt templates, builder functions, and domain-specific LLM instructions for the application.

## Design Principles
1. **Separation of Concerns:** Prompts are grouped by functional domain rather than residing in a monolithic file.
2. **Deterministic Schemas:** Pydantic schemas and models live in `app/models/` and are passed to client calls rather than embedded in prompt strings.
3. **No Hidden Logic:** Domain logic, branching, and fallbacks live in service/caller code; builder functions focus strictly on prompt rendering and truncation safety.
4. **Per-Prompt Versioning:** Every prompt or builder exports a semantic version constant (e.g. `*_PROMPT_VERSION = "v1"`).

---

## Package Structure

| Module | Responsibility | Key Exports |
| :--- | :--- | :--- |
| `base.py` | System prompt & shared core instructions | `SYSTEM_PROMPT`, `STRICT_JSON_INSTRUCTION` |
| `analysis.py` | Candidate matching, executive summaries, domain mismatch | `build_executive_summary_prompt()`, `build_mismatch_prompt()`, `FRICTION_ANALYSIS_PROMPT`, `SAMPLE_ANALYSIS_PROMPT` |
| `roadmap.py` | 30-day, upskill, and career transition roadmaps | `build_upskill_roadmap_prompt()`, `build_transition_roadmap_prompt()`, `get_roadmap_weeks_count()`, `THIRTY_DAY_ROADMAP_PROMPT` |
| `ats.py` | Standard, transition, and advanced ATS optimization | `build_standard_ats_prompt()`, `build_transition_ats_prompt()`, `build_transition_tips_prompt()`, `ATS_OPTIMIZATION_PROMPT` |
| `seniority.py` | Seniority alignment and level gap analysis | `build_seniority_alignment_prompt()` |
| `extraction.py` | Candidate experience extraction LLM fallbacks | `build_experience_extraction_prompt()` |
| `career.py` | Long-term career guidance & interview question generation | `INTERVIEW_QUESTIONS_PROMPT`, `CAREER_ADVICE_PROMPT` |

---

## How to Import

All prompts and builder functions can be imported directly from `app.prompts`:

```python
from app.prompts import (
    build_executive_summary_prompt,
    build_upskill_roadmap_prompt,
    get_roadmap_weeks_count,
    THIRTY_DAY_ROADMAP_PROMPT,
    ATS_OPTIMIZATION_PROMPT,
)
```

Or from their specific domain submodules:

```python
from app.prompts.analysis import build_executive_summary_prompt
from app.prompts.roadmap import build_upskill_roadmap_prompt
```

---

## Testing & Fixtures

Byte-for-byte fidelity and caller integration tests are maintained under `backend/tests/`:
- `tests/test_prompts_render.py`: Verifies that rendered prompts match baseline golden fixtures across all parameter variants, branch conditions, and truncation limits.
- `tests/test_prompt_callers.py`: Runs real caller methods with mock LLM interception to verify that callers correctly invoke builders and pass prompt strings.

Run prompt tests with:
```bash
pytest tests/test_prompts_render.py tests/test_prompt_callers.py
```
