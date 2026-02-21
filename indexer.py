"""
Indexes scraped company data using sentence-transformers embeddings.
Uses a simple numpy-based vector store (pickle file) for Python 3.14 compatibility.
"""

import json
import os
import pickle

import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_PATH = os.path.join(os.path.dirname(__file__), "vector_index.pkl")
MODEL_NAME = "all-MiniLM-L6-v2"


def load_companies(path: str = "companies.json") -> list[dict]:
    """Load scraped company data from JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_document(company: dict) -> str:
    """Build a text document from company data for embedding."""
    parts = [
        f"Company: {company['name']}",
        f"Location: {company.get('location', 'Los Angeles, CA')}",
    ]
    if company.get("description"):
        parts.append(f"Description: {company['description']}")
    if company.get("services"):
        parts.append(f"Services: {company['services']}")
    if company.get("snippet"):
        parts.append(f"Summary: {company['snippet']}")
    if company.get("likely_chinese_owned"):
        parts.append("Note: Likely Chinese-owned / bilingual business")
    return "\n".join(parts)


def build_metadata(company: dict) -> dict:
    """Build metadata dict from company data."""
    return {
        "name": company.get("name", ""),
        "website": company.get("website", ""),
        "phones": company.get("phones", []),
        "emails": company.get("emails", []),
        "location": company.get("location", "Los Angeles, CA"),
        "likely_chinese_owned": company.get("likely_chinese_owned", False),
        "chinese_score": company.get("chinese_indicators", {}).get("score", 0),
    }


def run_indexer(companies_path: str = "companies.json") -> None:
    """Index all companies into a numpy-based vector store."""
    print("[*] Loading companies...")
    companies = load_companies(companies_path)
    print(f"    Loaded {len(companies)} companies")

    if not companies:
        print("[!] No companies to index. Run the scraper first.")
        return

    print(f"[*] Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    documents = []
    metadatas = []

    for company in companies:
        documents.append(build_document(company))
        metadatas.append(build_metadata(company))

    print(f"[*] Generating embeddings for {len(documents)} documents...")
    embeddings = model.encode(documents, show_progress_bar=True, convert_to_numpy=True)

    index_data = {
        "embeddings": embeddings,
        "documents": documents,
        "metadatas": metadatas,
    }

    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index_data, f)

    print(f"[*] Indexed {len(documents)} companies")
    print(f"    Index saved to: {INDEX_PATH}")
    print(f"    Embedding dim: {embeddings.shape[1]}")


if __name__ == "__main__":
    run_indexer()
