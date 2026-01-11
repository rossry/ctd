# CTD Document Archive

A public archive of regulatory documents for drug trials. Makes clinical trial data navigable and understandable for researchers, patients, and AI agents.

## Data Sources

| Drug | Indication | Source | License |
|------|------------|--------|---------|
| ALLN-177 (Reloxaliase) | Enteric hyperoxaluria | Allena Pharmaceuticals | Public (FDA) |
| ALLN-346 | Hyperuricemia/gout in CKD | Allena Pharmaceuticals | Public (FDA) |
| Divalent siRNA | Prion disease | [Eric Minikel et al.](https://github.com/ericminikel/divalent) | CC-BY-4.0 |

### Divalent siRNA Attribution

The Divalent siRNA IND application and research data are provided under CC-BY-4.0 license:

> Gentile JE, Corridon TL, Serack FE, et al. **Divalent siRNA for prion disease.** bioRxiv. 2024 Dec 5;2024.12.05.627039.
> https://doi.org/10.1101/2024.12.05.627039

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
│   ├── ALLN-177-Reloxaliase/
│   ├── ALLN-346/
│   ├── Divalent-siRNA/
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
