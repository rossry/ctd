# CTD Document Archive

A public archive of regulatory documents for drug trials (ALLN-177/Reloxaliase, ALLN-346). Makes clinical trial data navigable and understandable for researchers, patients, and AI agents.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/chavrusa/ctd.git
cd ctd

# Documents are not in git - obtain separately and place in /documents

# Generate table of contents
python generate_toc.py

# Serve locally
python -m http.server 8000
# Open http://localhost:8000
```

## Project Structure

```
/
├── documents/          # Document files (not in git)
│   ├── ALLN-346/
│   └── Supporting/
├── generate_toc.py     # Generates toc.json from documents/
├── index.html          # Current viewer (being replaced with Svelte)
├── toc.json            # Generated TOC (not in git)
├── METADATA.md         # Metadata format specification
└── ROADMAP.md          # Development plan
```

## Metadata

Each directory in `documents/` can have a `metadata.json` file providing titles, descriptions, and tags. See [METADATA.md](METADATA.md) for the full spec.

Example:
```json
{
  "_folder": {
    "drug": "ALLN-346",
    "summary": "Engineered uricase for hyperuricemia"
  },
  "CSR.pdf": {
    "title": "Clinical Study Report",
    "summary": "Phase 1 SAD study results",
    "tags": ["csr", "phase-1"]
  }
}
```

## Contributing

1. Fork the repo
2. Add/update metadata.json files to improve document descriptions
3. Submit a PR

## License

TBD
