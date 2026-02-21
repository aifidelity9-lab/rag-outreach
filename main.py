#!/usr/bin/env python3
"""
RAG Lead Generation & Email Outreach CLI

Usage:
    python main.py scrape    — Scrape company data from Google
    python main.py index     — Build ChromaDB vector index
    python main.py generate  — Generate personalized emails & call scripts
    python main.py all       — Run the full pipeline
"""

import sys
import os

# Ensure we're working from the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def cmd_scrape():
    from scraper import run_scraper
    use_seed = "--seed" in sys.argv
    run_scraper(use_seed=use_seed)


def cmd_index():
    from indexer import run_indexer
    run_indexer()


def cmd_generate():
    from generator import run_generator

    # Allow custom product pitch from stdin or use default
    product_pitch = None
    pitch_file = "product_pitch.txt"
    if os.path.exists(pitch_file):
        with open(pitch_file, "r", encoding="utf-8") as f:
            product_pitch = f.read().strip()
        print(f"[*] Loaded custom product pitch from {pitch_file}")

    run_generator(product_pitch=product_pitch)


def cmd_all():
    print("=" * 60)
    print("  RAG Lead Generation & Email Outreach — Full Pipeline")
    print("=" * 60)

    print("\n>>> STEP 1: Scraping companies...")
    cmd_scrape()

    print("\n>>> STEP 2: Building vector index...")
    cmd_index()

    print("\n>>> STEP 3: Generating personalized outreach...")
    cmd_generate()

    print("\n" + "=" * 60)
    print("  Pipeline complete!")
    print("=" * 60)


COMMANDS = {
    "scrape": cmd_scrape,
    "index": cmd_index,
    "generate": cmd_generate,
    "all": cmd_all,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("Available commands:")
        for cmd in COMMANDS:
            print(f"  {cmd}")
        sys.exit(1)

    command = sys.argv[1]
    COMMANDS[command]()


if __name__ == "__main__":
    main()
