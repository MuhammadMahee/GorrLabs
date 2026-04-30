# test_classifier.py
import asyncio
from arkive.utils.query_classifier import classify_query, should_use_agentic_path

tests = [
    "What is our refund policy?",
    "Summarize all HR policy changes this year",
    "How do our leave policies compare to industry standard?",
    "What are the steps to submit an expense claim?",
    "How does our Q3 performance compare to market benchmarks?",
    "What is 2 + 2?",
]

async def run():
    for query in tests:
        c = await classify_query(query)
        agentic = should_use_agentic_path(c)
        print(f"{'AGENTIC' if agentic else 'STANDARD':<10} {c.query_type.value:<12} {c.confidence:.2f}  {query[:50]}")

asyncio.run(run())
