"""
RAG-based email and call script generator using vector search + Ollama (local LLM).
Retrieves relevant company profiles and generates personalized outreach.
"""

import csv
import json
import os
import pickle

import numpy as np
import requests
from sentence_transformers import SentenceTransformer

INDEX_PATH = os.path.join(os.path.dirname(__file__), "vector_index.pkl")
MODEL_NAME = "all-MiniLM-L6-v2"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "emails_output")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"

DEFAULT_PRODUCT_PITCH = """
We offer an AI-powered Auto Entry Summary product for customs brokers and importers that:
- Automatically generates customs entry summaries (CF-7501) from shipping documents
- Extracts data from commercial invoices, packing lists, and bills of lading using AI/OCR
- Auto-classifies HTS codes based on product descriptions
- Reduces manual data entry time by 80% — no more typing entry after entry
- Integrates with existing customs software (NetCHB, CargoWise, ABI/ACS)
- Supports English and Chinese documents (中英文单据都能处理)
- Catches errors before filing — reduces CBP rejections and penalties
- Handles FDA, USDA, and other PGA data requirements automatically
- Provides dashboard for tracking entry status, duty payments, and compliance

Pricing starts at $199/month per broker license with volume discounts.
Free trial available — process 50 entries free.
"""


def load_index() -> dict:
    """Load the vector index from disk."""
    with open(INDEX_PATH, "rb") as f:
        return pickle.load(f)


def retrieve_companies(
    index_data: dict,
    model: SentenceTransformer,
    query: str = "customer service company",
    n_results: int = 20,
) -> list[dict]:
    """Query the vector index for relevant companies using cosine similarity."""
    query_embedding = model.encode([query], convert_to_numpy=True)

    embeddings = index_data["embeddings"]

    # Cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normalized = embeddings / norms

    query_norm = np.linalg.norm(query_embedding)
    if query_norm == 0:
        query_norm = 1
    query_normalized = query_embedding / query_norm

    similarities = (normalized @ query_normalized.T).flatten()

    n = min(n_results, len(similarities))
    top_indices = np.argsort(similarities)[::-1][:n]

    companies = []
    for idx in top_indices:
        meta = index_data["metadatas"][idx]
        companies.append({
            "document": index_data["documents"][idx],
            "similarity": float(similarities[idx]),
            "name": meta.get("name", ""),
            "website": meta.get("website", ""),
            "phones": meta.get("phones", []),
            "emails": meta.get("emails", []),
            "location": meta.get("location", ""),
            "likely_chinese_owned": meta.get("likely_chinese_owned", False),
            "chinese_score": meta.get("chinese_score", 0),
        })

    return companies


def call_ollama(prompt: str) -> str:
    """Call Ollama's local API and return the response text."""
    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 2000,
            },
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def generate_email(company: dict, product_pitch: str) -> dict:
    """Use Ollama to generate a personalized cold email and call script."""

    is_chinese = company.get("likely_chinese_owned", False)

    chinese_script = '''Since this appears to be a Chinese-owned customs broker, write a phone call script in Chinese (Mandarin).
- Start with a polite Chinese greeting
- Introduce yourself and the AI customs entry product naturally in Chinese
- Mention specific pain points: 手动录入报关数据太慢, 容易出错, CBP退单
- Key selling points: AI自动从发票提取数据填写报关单, 支持中英文单据, 减少80%录入时间
- Handle objections: 我们已经用NetCHB了 → 我们跟NetCHB兼容，是补充不是替代
- End with scheduling a demo: 可以给您做个免费演示'''

    english_script = '''Write a brief phone call script in English.
- Professional opening referencing their customs brokerage
- Quick value proposition: AI that auto-generates entry summaries from shipping docs
- Handle objection: "We already use NetCHB/CargoWise" → "We integrate with those, we auto-fill the data"
- Close with scheduling a demo / free trial'''

    call_script_instructions = chinese_script if is_chinese else english_script

    prompt = f"""You are a sales outreach specialist selling AI customs entry software to customs brokers and import companies. Generate personalized outreach materials for the following company.

## Target Company Profile
{company['document']}

Website: {company['website']}
Phone(s): {', '.join(company['phones']) if company['phones'] else 'Not available'}
Email(s): {', '.join(company['emails']) if company['emails'] else 'Not available'}
Likely Chinese-owned: {'Yes' if is_chinese else 'No'}

## Product We Are Selling
{product_pitch}

## Instructions

Generate TWO pieces of content:

### 1. Cold Email (in English)
- Subject line referencing their customs brokerage business specifically
- Personalized opening showing you know their company and the pain of manual entry filing
- Clear value proposition: AI auto-fills entry summaries from shipping docs, saves hours of data entry
- Mention compatibility with their likely software (NetCHB, CargoWise, ABI)
- Specific ROI: reduce entry processing time from 30 min to 5 min per entry
- Clear call to action (schedule a demo / free trial)
- Professional but warm tone
- Keep it under 200 words

### 2. Phone Call Script
{call_script_instructions}

Format your response exactly as:
---EMAIL START---
Subject: [subject line]

[email body]
---EMAIL END---

---CALL SCRIPT START---
[call script]
---CALL SCRIPT END---
"""

    content = call_ollama(prompt)

    # Parse email
    email_text = ""
    if "---EMAIL START---" in content and "---EMAIL END---" in content:
        email_text = content.split("---EMAIL START---")[1].split("---EMAIL END---")[0].strip()
    else:
        email_text = content

    # Parse call script
    call_script = ""
    if "---CALL SCRIPT START---" in content and "---CALL SCRIPT END---" in content:
        call_script = content.split("---CALL SCRIPT START---")[1].split("---CALL SCRIPT END---")[0].strip()

    return {
        "email": email_text,
        "call_script": call_script,
        "raw_response": content,
    }


def run_generator(
    product_pitch: str | None = None,
    query: str = "customer service BPO call center company",
    max_companies: int = 20,
) -> None:
    """Run the full generation pipeline."""
    if product_pitch is None:
        product_pitch = DEFAULT_PRODUCT_PITCH

    # Check Ollama is running
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        if not any(OLLAMA_MODEL in m for m in models):
            print(f"[!] Model '{OLLAMA_MODEL}' not found. Available: {models}")
            print(f"    Run: ollama pull {OLLAMA_MODEL}")
            return
        print(f"[*] Ollama running with model: {OLLAMA_MODEL}")
    except Exception as e:
        print(f"[!] Cannot connect to Ollama: {e}")
        print("    Start it with: brew services start ollama")
        return

    print("[*] Loading vector index...")
    try:
        index_data = load_index()
    except FileNotFoundError:
        print(f"[!] Index not found at {INDEX_PATH}")
        print("    Run 'python main.py index' first.")
        return

    print(f"[*] Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)

    print(f"[*] Retrieving companies (query: '{query}')...")
    companies = retrieve_companies(index_data, model, query=query, n_results=max_companies)
    print(f"    Found {len(companies)} companies")

    if not companies:
        print("[!] No companies found. Run scraper and indexer first.")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    summary_rows = []

    for i, company in enumerate(companies):
        name = company["name"] or f"Company_{i}"
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in name)[:50].strip()
        safe_name = safe_name.replace(" ", "_")

        print(f"\n[*] ({i+1}/{len(companies)}) Generating outreach for: {name}")
        print(f"    Chinese-owned: {'Yes' if company['likely_chinese_owned'] else 'No'}")
        print(f"    Phones: {company['phones']}")
        print(f"    Similarity: {company['similarity']:.3f}")

        try:
            result = generate_email(company, product_pitch)

            # Save individual file
            filename = f"{safe_name}.txt"
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Company: {name}\n")
                f.write(f"Website: {company['website']}\n")
                f.write(f"Phone(s): {', '.join(company['phones'])}\n")
                f.write(f"Email(s): {', '.join(company['emails'])}\n")
                f.write(f"Chinese-owned: {'Yes' if company['likely_chinese_owned'] else 'No'}\n")
                f.write("=" * 60 + "\n\n")
                f.write("COLD EMAIL:\n")
                f.write("-" * 40 + "\n")
                f.write(result["email"] + "\n\n")
                f.write("PHONE CALL SCRIPT:\n")
                f.write("-" * 40 + "\n")
                f.write(result["call_script"] + "\n")

            print(f"    Saved: {filepath}")

            summary_rows.append({
                "company_name": name,
                "phone": "; ".join(company["phones"]),
                "email": "; ".join(company["emails"]),
                "website": company["website"],
                "chinese_owned": "Yes" if company["likely_chinese_owned"] else "No",
                "outreach_file": filename,
            })

        except Exception as e:
            print(f"    [!] Failed to generate for {name}: {e}")

    # Write summary CSV
    csv_path = os.path.join(OUTPUT_DIR, "summary.csv")
    if summary_rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"\n[*] Summary CSV saved to: {csv_path}")

    print(f"\n[*] Done! Generated outreach for {len(summary_rows)} companies.")
    print(f"    Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    run_generator()
