Title
Market Analysis Tool (DeGiro Only)

Overview
Market Analysis Tool is a desktop utility that automates fundamental company research by combining DeGiro data with LLM‑assisted analysis. Search tickers, pull key fundamentals from DeGiro, and generate professional PDF reports or compare multiple companies side by side. Originally built as a personal research tool, this project demonstrates practical API integration, prompt engineering, and end‑to‑end report generation in Python.

Key features

DeGiro integration: Login and fetch instrument data via DeGiro.

LLM‑assisted analysis: Uses Perplexity API to generate structured, data‑driven commentary.

Report generation: Export clean, readable PDF reports (single‑company or comparison).

Company search and selection: Search names/symbols, add to a selection list, analyze in batch.

Configurable prompts: Choose model and set guidance for tone, depth, and structure.

Local, lightweight app: Simple GUI for non‑technical use.

Screenshots

assets/screenshot-ui.png

assets/sample-report.pdf

assets/sample-compare.pdf

Tech stack

Python (core logic, API clients, report generation)

GUI: Tkinter 

HTTP/REST: DeGiro endpoints + Perplexity API

PDF: FPDF

Optional: python‑dotenv for environment variables

Project structure
Adjust to your repo.

app/

gui.py # UI components (login, search, selections)

degiro_client.py # Auth + endpoints for DeGiro

perplexity_client.py # LLM calls and prompt templates

analysis.py # Analysis workflow and formatting

report.py # PDF generation

config.py # Settings, model choices, constants

assets/ # Icons, screenshots, sample outputs

.env.example # Template for environment variables

requirements.txt # Dependencies

README.md # This file

LICENSE # Optional

Security and credentials

Do not commit real credentials or API keys.

Use a local .env file and keep it out of Git (see .gitignore).

DeGiro sessions/2FA: follow DeGiro’s security requirements.

.env.example
Copy to .env and fill with your values.
PERPLEXITY_API_KEY=pk-xxxxxxxxxxxxxxxxxxxxxxxx
DEGIRO_USERNAME=your_username
DEGIRO_PASSWORD=your_password
DEGIRO_API_BASE=https://[degiro-endpoint]
MODEL_NAME=sonar-pro

Installation
Prerequisites

Python 3.10+

Perplexity API key

DeGiro account (required). Other brokers are not supported in this release.

Steps

Clone
git clone https://github.com/DeltaKL/MarketAnalysis.git
cd MarketAnalysis

Create virtual environment
python -m venv .venv

Windows
.venv\Scripts\activate

macOS/Linux
source .venv/bin/activate

Install dependencies
pip install -r requirements.txt

Configure environment
cp .env.example .env

Edit .env with your keys and credentials
Usage
GUI (default)
python -m app.gui

Login with DeGiro credentials

Search companies, add to Selected Companies

Choose model and analysis options

Generate individual reports or compare companies

CLI (if supported)
python -m app.main --ticker AAPL --report out/AAPL.pdf

How it works

Data retrieval: Pulls symbol metadata and fundamentals from DeGiro.

Prompt assembly: Builds a structured prompt with fetched data + your guidance.

LLM call: Sends prompt to Perplexity (e.g., sonar‑pro) and receives a draft analysis.

Report generation: Formats results into a clean PDF with consistent sections.

Comparison mode: Summarizes and contrasts multiple companies side by side.

Configuration

Model selection: Set default in .env (MODEL_NAME) or select in UI.

Analysis guidance: Configure tone/instructions (e.g., “maintain a professional, data‑driven tone”).

Output paths: Adjust output directories in config.py.

Limitations

Supports DeGiro only (current release).

Intended for personal research and educational use; not financial advice.

LLM outputs may contain inaccuracies—verify important claims.

Broker APIs can rate‑limit or change; update degiro_client.py as needed.

Roadmap

Additional broker support

CSV/Excel export of key metrics

Response caching for fewer API calls

Provider plug‑ins (OpenAI, Anthropic, etc.)

Optional: citation extraction and source links in reports

Troubleshooting

Login fails: Verify DeGiro credentials and session/2FA.

No results: Try exact ticker symbols.

API errors: Check keys, endpoints, and network connectivity.

PDF not created: Confirm output folder and file permissions.

Rate limits: Increase delays/retries in config.py.

Contributing
Issues and pull requests are welcome. For bug reports, include steps to reproduce without sharing credentials or private data.

License
MIT (recommended) or choose your preferred license.

Author
Daan van Keulen — https://github.com/DeltaKL

Notes for reviewers/employers
This project was created as a personal research tool and portfolio piece. It demonstrates:

Python application development with external APIs

Prompt engineering for consistent LLM outputs

End‑to‑end report generation for non‑technical users
Sample reports and a brief walkthrough are available on request.

