# RAG Outreach — AI Lead Gen for Customs Brokers

RAG-powered lead generation and personalized email/call script generator targeting customs brokers (CHB) and import companies in Los Angeles, with a focus on Chinese-owned businesses.

## How It Works

```
[Scraper] → [Company Data (JSON)] → [Embeddings + Vector Search] → [RAG Query + Ollama LLM] → [Personalized Emails + 中文 Call Scripts]
```

1. **Scrape** — Finds customs brokers via search engines (DuckDuckGo/Google) with fallback to curated seed data. Visits company websites to extract phone numbers, emails, and Chinese ownership indicators.
2. **Index** — Embeds company profiles using `sentence-transformers` (all-MiniLM-L6-v2) and stores them in a local numpy-based vector index.
3. **Generate** — Retrieves relevant companies via cosine similarity, then uses Ollama (Qwen 2.5) to generate:
   - **Cold email** (English) — personalized with company-specific pain points around manual customs entry
   - **Phone call script** (中文 Mandarin) — for Chinese-owned brokers, or English for others

## Product Being Sold

AI-powered **Auto Entry Summary** for customs brokers:
- Auto-generates CF-7501 entry summaries from shipping documents (invoices, packing lists, BOLs)
- OCR + AI extraction — no manual data entry
- HTS code auto-classification
- Compatible with NetCHB, CargoWise, ABI
- Supports English and Chinese documents

## Setup

```bash
# Clone
git clone https://github.com/aifidelity9-lab/rag-outreach.git
cd rag-outreach

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Install Ollama (macOS)
brew install ollama
brew services start ollama
ollama pull qwen2.5:7b
```

## Usage

```bash
# Run each step
python main.py scrape      # Scrape company data → companies.json
python main.py index       # Build vector index → vector_index.pkl
python main.py generate    # Generate emails → emails_output/

# Or run full pipeline
python main.py all
```

## Output

```
emails_output/
├── Speed_C_CHB_美国速通清关.txt    # Email + Chinese call script
├── Omega_CHB_International.txt     # Email + English call script
├── C__R_Customs_Brokers_中美报关.txt
├── ...
└── summary.csv                     # Master contact list
```

Each `.txt` file contains:
- Company contact info (phone, email, website)
- Personalized cold email
- Phone call script (中文 for Chinese-owned, English for others)

`summary.csv` has all companies with: name, phone, email, website, chinese_owned flag.

## Tech Stack

| Component | Tool | Cost |
|-----------|------|------|
| Web scraping | requests + BeautifulSoup | Free |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Free, local |
| Vector search | numpy cosine similarity | Free, local |
| LLM generation | Ollama + Qwen 2.5 7B | Free, local |

Everything runs **100% locally and offline** (after initial model download). No API keys needed.

## Customization

- **Product pitch** — Create `product_pitch.txt` in the project root to override the default pitch
- **LLM model** — Change `OLLAMA_MODEL` in `generator.py` (e.g. `llama3.1:8b`, `qwen2.5:7b`)
- **Seed data** — Edit `SEED_COMPANIES` in `scraper.py` to add/remove target companies
