"""Gemini Deep Research API client.

Wraps the google-genai SDK to provide a simple interface for running
deep research queries and polling for results, saving sources/citations
from the DR output alongside the text.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Polling configuration
_POLL_INTERVAL_SEC = 10
_POLL_TIMEOUT_WARN_SEC = 1800  # log a warning after 30 min
_POLL_TIMEOUT_HARD_SEC = 3600  # hard cutoff after 1 hour


@dataclass
class DeepResearchResult:
    """Result from a deep research query."""

    text: str
    status: str  # "completed" | "failed" | "timeout"
    elapsed_sec: float
    interaction_id: str = ""
    sources: list[dict] = field(default_factory=list)  # [{url, title}]
    annotations: list[dict] = field(default_factory=list)  # raw citation annotations


class DeepResearchClient:
    """Client for Gemini Deep Research API.

    Usage::

        client = DeepResearchClient(api_key="...")
        result = client.research("How to use the Pandas API to read and aggregate CSV files")
        print(result.text)
        print(result.sources)  # [{url: ..., title: ...}, ...]
    """

    def __init__(
        self,
        api_key: str | None = None,
        agent: str = "deep-research-pro-preview-12-2025",
    ):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self._api_key:
            raise ValueError("No API key provided. Set GEMINI_API_KEY or pass api_key=")
        self._agent = agent

        # Lazy import to avoid hard dependency at module level
        from google import genai

        self._client = genai.Client(api_key=self._api_key)

    @staticmethod
    def _extract_text(interaction) -> str:
        """Extract the final report text (tolerant across SDK schemas)."""
        text = getattr(interaction, "output_text", None)
        if text:
            return text
        outputs = getattr(interaction, "outputs", None) or []
        parts = [getattr(o, "text", None) for o in outputs if getattr(o, "type", "text") == "text"]
        parts = [x for x in parts if x]
        return parts[-1] if parts else ""

    @staticmethod
    def _extract_sources(interaction) -> tuple[list[dict], list[dict]]:
        """Extract sources and annotations from a completed interaction.

        Recursively walks the interaction payload and collects citation-like
        dicts (anything with a url), tolerating SDK schema changes.

        Returns:
            (sources, annotations) where sources is a list of {url, title}
            dicts and annotations is a list of raw annotation dicts.
        """
        sources: list[dict] = []
        annotations: list[dict] = []
        seen_urls: set[str] = set()

        try:
            dump = interaction.model_dump(exclude_none=True)
        except Exception:
            return sources, annotations

        def walk(node):
            if isinstance(node, dict):
                url = node.get("url") or node.get("uri")
                if isinstance(url, str) and url.startswith("http"):
                    ann = {k: node[k] for k in ("type", "start_index", "end_index", "url", "uri", "title", "text") if k in node}
                    annotations.append(ann)
                    if url not in seen_urls:
                        seen_urls.add(url)
                        sources.append({"url": url, "title": node.get("title") or ""})
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        for key in ("steps", "outputs", "annotations"):
            walk(dump.get(key))

        return sources, annotations

    def research(self, query: str) -> DeepResearchResult:
        """Run a deep research query synchronously (blocking).

        Polls until the interaction reaches 'completed' or 'failed'.
        No hard timeout — the caller is responsible for killing the
        process if an external deadline is needed.

        Args:
            query: The research question or prompt.

        Returns:
            DeepResearchResult with the research output.
        """
        start = time.time()
        warned = False

        logger.info("Starting deep research query (%d char)", len(query))

        try:
            interaction = self._client.interactions.create(
                input=query,
                agent=self._agent,
                background=True,
            )
        except Exception as e:
            logger.error("Failed to create deep research interaction: %s", e)
            return DeepResearchResult(
                text="",
                status="failed",
                elapsed_sec=time.time() - start,
            )

        interaction_id = interaction.id
        logger.info("Deep research interaction created: %s", interaction_id)

        # Poll for completion
        while True:
            try:
                interaction = self._client.interactions.get(interaction_id)
            except Exception as e:
                logger.warning("Poll error: %s", e)
                time.sleep(_POLL_INTERVAL_SEC)
                continue

            if interaction.status == "completed":
                elapsed = time.time() - start
                output_text = self._extract_text(interaction)

                # Extract sources and annotations
                try:
                    sources, annotations = self._extract_sources(interaction)
                except Exception as src_exc:
                    logger.warning("Failed to extract sources: %s", src_exc)
                    sources, annotations = [], []

                logger.info(
                    "Deep research completed in %.1fs (%d chars, %d sources)",
                    elapsed,
                    len(output_text),
                    len(sources),
                )
                return DeepResearchResult(
                    text=output_text,
                    status="completed",
                    elapsed_sec=elapsed,
                    interaction_id=interaction_id,
                    sources=sources,
                    annotations=annotations,
                )

            if interaction.status == "failed":
                elapsed = time.time() - start
                error_msg = getattr(interaction, "errors", None) or getattr(interaction, "error", "unknown error")
                logger.error("Deep research failed after %.1fs: %s", elapsed, error_msg)
                return DeepResearchResult(
                    text="",
                    status="failed",
                    elapsed_sec=elapsed,
                    interaction_id=interaction_id,
                )

            # Terminal statuses that won't transition to completed
            if interaction.status in ("cancelled", "requires_action", "incomplete", "budget_exceeded"):
                elapsed = time.time() - start
                logger.error(
                    "Deep research terminated with status '%s' after %.1fs",
                    interaction.status,
                    elapsed,
                )
                return DeepResearchResult(
                    text="",
                    status=interaction.status,
                    elapsed_sec=elapsed,
                    interaction_id=interaction_id,
                )

            # Hard timeout — cancel the interaction and return
            elapsed = time.time() - start
            if elapsed > _POLL_TIMEOUT_HARD_SEC:
                logger.error(
                    "Deep research hard timeout after %.0fs — cancelling interaction %s",
                    elapsed,
                    interaction_id,
                )
                try:
                    self._client.interactions.cancel(interaction_id)
                except Exception as cancel_exc:
                    logger.warning("Failed to cancel interaction: %s", cancel_exc)
                return DeepResearchResult(
                    text="",
                    status="timeout",
                    elapsed_sec=elapsed,
                    interaction_id=interaction_id,
                )

            # Warn once if polling for a long time
            if not warned and elapsed > _POLL_TIMEOUT_WARN_SEC:
                logger.warning(
                    "Deep research still running after %.0fs — still polling...",
                    elapsed,
                )
                warned = True

            time.sleep(_POLL_INTERVAL_SEC)
