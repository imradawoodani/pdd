"""
Token counting, cost estimation, and context auditing utilities with persistent caching.

Uses litellm for model-aware token counting and context window lookup.
Falls back to tiktoken for unknown models.
Loads model pricing from .pdd/llm_model.csv.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional, Dict, List, Set

import litellm
import tiktoken

from pdd.path_resolution import get_default_resolver
from pdd.preprocess import compute_user_intent_paths
from pdd.server.models import (
    ContextAudit,
    CostEstimate,
    TokenBreakdown,
    TokenMetrics,
)

logger = logging.getLogger(__name__)

# Tiktoken fallback encoding for models litellm cannot identify
_FALLBACK_ENCODING = "cl100k_base"

# Hard cap (seconds) on any individual litellm provider-detection call.
_LITELLM_CALL_TIMEOUT_SEC = 5.0

# SQLite cache location
CACHE_DB_PATH = ".pdd/cache/context_audit.db"


def _call_litellm_with_timeout(
    fn: Callable[..., Any],
    *args: Any,
    timeout: Optional[float] = None,
    **kwargs: Any,
) -> Any:
    """Run a litellm call in a worker thread with a hard timeout."""
    effective_timeout = timeout if timeout is not None else _LITELLM_CALL_TIMEOUT_SEC
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="litellm-probe")
    try:
        future = executor.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=effective_timeout)
        except FuturesTimeoutError as exc:
            future.cancel()
            raise TimeoutError(
                f"litellm call {getattr(fn, '__qualname__', repr(fn))} timed out"
                f" after {effective_timeout:.1f}s"
            ) from exc
    finally:
        executor.shutdown(wait=False)


@lru_cache(maxsize=1)
def _get_fallback_encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_FALLBACK_ENCODING)


def _tiktoken_fallback(text: str) -> int:
    encoding = _get_fallback_encoding()
    return len(encoding.encode(text))


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in text using litellm, with tiktoken fallback."""
    if not text:
        return 0
    messages = [{"role": "user", "content": text}]
    try:
        return _call_litellm_with_timeout(
            litellm.token_counter, model=model, messages=messages
        )
    except Exception:
        return _tiktoken_fallback(text)


def get_context_limit(model: str) -> Optional[int]:
    """Get the input context window size for a model via litellm."""
    try:
        info = _call_litellm_with_timeout(litellm.get_model_info, model)
        return info.get("max_input_tokens") if info else None
    except Exception:
        return None


@lru_cache(maxsize=1)
def _load_model_pricing(csv_path: str) -> Dict[str, float]:
    pricing: Dict[str, float] = {}
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                model = row.get("model", "")
                input_cost = row.get("input", "0")
                try:
                    pricing[model] = float(input_cost)
                except ValueError:
                    continue
    except Exception:
        pass
    return pricing


def estimate_cost(
    token_count: int,
    model: str,
    pricing_csv: Optional[Path] = None,
) -> Optional[CostEstimate]:
    """Estimate input cost from pricing CSV."""
    if pricing_csv is None or not pricing_csv.exists():
        return None
    pricing = _load_model_pricing(str(pricing_csv))
    if not pricing:
        return None

    cost_per_million = pricing.get(model)
    matched_model = model

    if cost_per_million is None:
        model_lower = model.lower()
        for csv_model, cost in pricing.items():
            if model_lower in csv_model.lower() or csv_model.lower() in model_lower:
                cost_per_million = cost
                matched_model = csv_model
                break

    if cost_per_million is None:
        for default_model in ["claude-3-5-sonnet-latest", "gpt-4o"]:
            if default_model in pricing:
                cost_per_million = pricing[default_model]
                matched_model = default_model
                break

    if cost_per_million is None:
        return None

    input_cost = (token_count / 1_000_000) * cost_per_million
    return CostEstimate(
        input_cost=input_cost,
        model=matched_model,
        tokens=token_count,
        cost_per_million=cost_per_million,
    )


def get_token_metrics(
    text: str,
    model: str = "gpt-4o",
    pricing_csv: Optional[Path] = None,
) -> TokenMetrics:
    """Get comprehensive token metrics."""
    token_count = count_tokens(text, model)
    context_limit = get_context_limit(model)
    usage = (token_count / context_limit) * 100 if context_limit else None
    cost = estimate_cost(token_count, model, pricing_csv)
    return TokenMetrics(
        token_count=token_count,
        context_limit=context_limit,
        context_usage_percent=usage,
        cost_estimate=cost,
    )


def _get_associated_files(prompt_path: Path) -> Set[Path]:
    """Find associated test, example, and context files by convention."""
    # Strip language suffixes
    name = prompt_path.stem
    name = re.sub(r"_(python|typescript|javascript|bash|makefile|restructuredtext|LLM)$", "", name)
    
    project_root = Path.cwd()
    associated = set()
    
    # Common search patterns
    patterns = [
        f"**/{name}_test.*",
        f"**/test_{name}.*",
        f"**/{name}.test.*",
        f"**/{name}_example.*",
        f"**/{name}_example_*.*",
        f"**/example_{name}.*",
    ]
    
    search_dirs = ["tests", "examples", "context"]
    for sdir in search_dirs:
        dir_path = project_root / sdir
        if dir_path.exists():
            for pattern in patterns:
                for match in dir_path.glob(pattern):
                    if match.is_file():
                        associated.add(match)
    
    return associated


def get_tree_hash(prompt_path_str: str) -> str:
    """Compute recursive SHA-256 tree hash of prompt and dependencies."""
    prompt_path = Path(prompt_path_str)
    if not prompt_path.exists():
        return ""

    hasher = hashlib.sha256()
    seen: Set[Path] = set()
    to_process: List[Path] = [prompt_path]
    
    # Also include associated files in the tree hash
    to_process.extend(_get_associated_files(prompt_path))

    while to_process:
        current = to_process.pop().resolve()
        if current in seen or not current.exists() or not current.is_file():
            continue
        seen.add(current)
        
        with open(current, "rb") as f:
            hasher.update(f.read())
            
        # Scan for includes if it's a prompt or text file
        if current.suffix in (".prompt", ".md", ".txt", ".py", ".ts", ".tsx"):
            try:
                content = current.read_text(encoding="utf-8")
                paths = compute_user_intent_paths(content)
                resolver = get_default_resolver()
                for p in paths:
                    try:
                        resolved = resolver.resolve_include(p)
                        if resolved.exists():
                            to_process.append(resolved)
                    except Exception:
                        continue
            except Exception:
                continue

    return hasher.hexdigest()


def _init_cache():
    """Ensure SQLite cache DB and table exist."""
    db_path = Path(CACHE_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_audit (
                cache_key TEXT PRIMARY KEY,
                prompt_path TEXT,
                tree_hash TEXT,
                model TEXT,
                data JSON,
                timestamp REAL
            )
            """
        )


def get_context_audit(prompt_path: str, model: str) -> ContextAudit:
    """Get or compute context audit for a prompt, with persistent caching."""
    _init_cache()
    tree_hash = get_tree_hash(prompt_path)
    if not tree_hash:
        # Fallback for missing file
        return ContextAudit(prompt_path, "", get_token_metrics("", model))

    cache_key = hashlib.sha256(f"{tree_hash}:{model}".encode()).hexdigest()
    
    with sqlite3.connect(CACHE_DB_PATH) as conn:
        row = conn.execute(
            "SELECT data FROM context_audit WHERE cache_key = ?", (cache_key,)
        ).fetchone()
        if row:
            return ContextAudit.model_validate_json(row[0])

    # Cache miss - compute it
    from pdd.preprocess import preprocess
    
    prompt_file = Path(prompt_path)
    content = prompt_file.read_text(encoding="utf-8")
    
    # Categorize and count tokens for each part
    breakdown = TokenBreakdown()
    breakdown.body = count_tokens(content, model)
    
    # Find all includes
    paths = compute_user_intent_paths(content)
    resolver = get_default_resolver()
    
    for p in paths:
        try:
            resolved = resolver.resolve_include(p)
            if not resolved.exists():
                continue
            
            part_content = resolved.read_text(encoding="utf-8")
            tokens = count_tokens(part_content, model)
            
            # Categorize
            rel_path = str(resolved.relative_to(Path.cwd()))
            if "tests/" in rel_path or rel_path.endswith(("_test.py", "_test.ts", ".test.tsx", ".test.ts")):
                breakdown.tests += tokens
            elif "examples/" in rel_path:
                breakdown.examples += tokens
            elif "context/" in rel_path:
                breakdown.grounding += tokens
            else:
                breakdown.includes += tokens
        except Exception:
            continue

    # Handle <web> tags heuristic
    web_tags = re.findall(r"<web>(.*?)</web>", content)
    for _ in web_tags:
        # Heuristic: 500 tokens per web grounding if not cached
        breakdown.grounding += 500

    # Fully hydrate for total count
    hydrated = preprocess(content, recursive=True)
    metrics = get_token_metrics(hydrated, model, Path(".pdd/llm_model.csv"))
    metrics.breakdown = breakdown
    
    audit = ContextAudit(prompt_path, tree_hash, metrics)
    
    # Save to cache
    with sqlite3.connect(CACHE_DB_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO context_audit (cache_key, prompt_path, tree_hash, model, data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (cache_key, prompt_path, tree_hash, model, audit.model_dump_json(), time.time())
        )
        
    return audit
