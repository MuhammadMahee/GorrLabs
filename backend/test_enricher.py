import asyncio
from arkive.utils.contextual_enricher import enrich_chunks

class FakeDoc:
    def __init__(self, content):
        self.page_content = content
        self.metadata = {"name": "HR Policy Manual"}

async def test():
    docs = [
        FakeDoc("Employees are entitled to 21 days of annual leave per calendar year."),
        FakeDoc("All expense claims must be submitted within 30 days of the expense date."),
        FakeDoc("Remote work requests must be approved by the direct line manager."),
    ]

    print("BEFORE enrichment:")
    for i, doc in enumerate(docs):
        print(f"  Chunk {i+1}: {doc.page_content[:80]}...")

    enriched = await enrich_chunks(docs, document_title="HR Policy Manual")

    print("\nAFTER enrichment:")
    for i, doc in enumerate(enriched):
        print(f"  Chunk {i+1}:\n{doc.page_content}\n")

asyncio.run(test())
