# Path B of dual-path content: live web search for factually accurate, current grounding.
# Uses DuckDuckGo (ddgs). Degrades gracefully to None when search is unavailable.

import logging
import sys
import os
from typing import Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

logger = logging.getLogger(__name__)


class FactualAgent:
    '''Gathers factual grounding for a topic via live web search.'''

    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    def gather_facts(self, query: str) -> Optional[str]:
        '''Returns a formatted findings block, or None if search yields nothing / fails.'''
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        logger.info("Factual: searching the web for grounding (query=%r)", query)
        try:
            # Imported lazily so the module imports cleanly without the dependency loaded.
            from ddgs import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self.max_results))

            if not results:
                logger.info("Factual: no web results for %r", query)
                return None

            blocks = []
            for r in results:
                title = (r.get("title") or "").strip()
                body = (r.get("body") or "").strip()
                href = (r.get("href") or r.get("url") or "").strip()
                blocks.append(f"- {title}\n  {body}\n  Source: {href}")
            logger.info("Factual: gathered %d result(s)", len(results))
            return "\n".join(blocks)
        except Exception:
            logger.exception("Factual: web search error")
            return None


if __name__ == "__main__":
    agent = FactualAgent()
    print(agent.gather_facts("latest Python data science libraries 2025"))
