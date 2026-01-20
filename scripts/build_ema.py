#!/usr/bin/env python3
"""Build EMA (European Medicines Agency) accession structure.

Creates the RDCP-E26-EMA accession with:
- files/{product-number}/EMA/ - symlinks to actual files in _raw/
- By-ATC/ - hierarchical view by ATC classification codes

Symlinks are intentionally broken until files are downloaded on-demand.

Usage:
    python scripts/build_ema.py              # Build structure
    python scripts/build_ema.py --clean      # Remove and rebuild
    python scripts/build_ema.py --dry-run    # Show what would be created
"""

import argparse
import json
import os
import re
import shutil
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

# Import our modules
from ema_atc_codes import get_atc_hierarchy
from view_utils import (
    ViewStatistics,
    create_symlink_safe,
    escape_for_path,
    extract_title_from_ema_name,
    format_dated_filename,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "documents" / "_raw"
DOCUMENTS_DIR = PROJECT_DIR / "documents"
EMA_ACCESSION = "RDCP-E26-EMA"
EMA_ACCESSION_DIR = DOCUMENTS_DIR / EMA_ACCESSION

# Paths to EMA JSON index files
EMA_JSON_DIR = RAW_DIR / "www.ema.europa.eu" / "en" / "documents" / "report"
MEDICINES_JSON = EMA_JSON_DIR / "medicines-output-medicines_json-report_en.json"
EPAR_DOCS_JSON = EMA_JSON_DIR / "documents-output-epar_documents_json-report_en.json"


@dataclass
class Medicine:
    """Represents an EMA medicine product."""
    product_number: str
    name: str
    category: str  # Human, Veterinary
    status: str    # Authorised, Withdrawn, etc.
    atc_code: str
    url: str
    marketing_auth_date: str | None = None

    @classmethod
    def from_json(cls, data: dict) -> "Medicine":
        return cls(
            product_number=data.get("ema_product_number", ""),
            name=data.get("name_of_medicine", ""),
            category=data.get("category", ""),
            status=data.get("medicine_status", ""),
            atc_code=data.get("atc_code_human", "") or data.get("atcvet_code_veterinary", ""),
            url=data.get("medicine_url", ""),
            marketing_auth_date=data.get("marketing_authorisation_date"),
        )


@dataclass
class Document:
    """Represents an EMA EPAR document."""
    id: str
    name: str
    doc_type: str
    url: str
    publish_date: str | None
    last_update_date: str | None
    medicine_name: str | None = None  # Extracted from name
    product_number: str | None = None  # Matched from medicines

    @classmethod
    def from_json(cls, data: dict) -> "Document":
        doc = cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            doc_type=data.get("type", ""),
            url=data.get("url", ""),
            publish_date=data.get("publish_date"),
            last_update_date=data.get("last_update_date"),
        )
        # Extract medicine name from document name
        doc.medicine_name = cls._extract_medicine_name(doc.name)
        return doc

    @staticmethod
    def _extract_medicine_name(name: str) -> str | None:
        """Extract medicine name from document name.

        Document names often have format:
        "Medicine Name : EPAR - Document Type"
        "Medicine Name - Document Type"
        """
        if not name:
            return None

        # Try "Name : EPAR" pattern first
        if " : EPAR" in name:
            return name.split(" : EPAR")[0].strip()

        # Try "Name :" pattern
        if " : " in name:
            return name.split(" : ")[0].strip()

        # Try "Name -" pattern (but not if it's "EPAR - ")
        if " - " in name and not name.startswith("EPAR - "):
            parts = name.split(" - ")
            # If first part looks like a medicine name (not a document type)
            first_part = parts[0].strip()
            doc_type_words = ['epar', 'public', 'assessment', 'report', 'scientific',
                             'product', 'information', 'summary', 'annex']
            if not any(word in first_part.lower() for word in doc_type_words):
                return first_part

        return None

    def get_date(self) -> str:
        """Get the document date in YYYY-MM-DD format."""
        date_str = self.publish_date or self.last_update_date
        if not date_str:
            return "0000-00-00"

        # Parse ISO format: "2009-12-17T01:00:00Z"
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return "0000-00-00"

    def get_title(self) -> str:
        """Get human-readable title for symlink name."""
        return extract_title_from_ema_name(self.name)

    def get_filename(self) -> str:
        """Get filename with date prefix."""
        date = self.get_date()
        title = self.get_title()
        # Get extension from URL
        ext = Path(urlparse(self.url).path).suffix or ".pdf"
        return format_dated_filename(date, title, ext)


def normalize_name(name: str) -> str:
    """Normalize a medicine name for matching.

    - Lowercase
    - Remove accents
    - Remove punctuation
    - Collapse whitespace
    """
    if not name:
        return ""

    # Lowercase
    name = name.lower()

    # Remove accents (NFD decomposition + strip combining marks)
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")

    # Remove punctuation except spaces
    name = re.sub(r"[^\w\s]", " ", name)

    # Collapse whitespace
    name = " ".join(name.split())

    return name


def load_medicines() -> dict[str, Medicine]:
    """Load medicines from JSON and return dict keyed by product number."""
    if not MEDICINES_JSON.exists():
        print(f"ERROR: Medicines JSON not found: {MEDICINES_JSON}")
        print("Run 'python scripts/download_ema.py --json-only' first.")
        return {}

    with open(MEDICINES_JSON) as f:
        data = json.load(f)

    # Handle both list and dict formats
    records = data if isinstance(data, list) else data.get("data", [])

    medicines = {}
    for record in records:
        med = Medicine.from_json(record)
        if med.product_number:
            medicines[med.product_number] = med

    return medicines


def load_documents() -> list[Document]:
    """Load EPAR documents from JSON."""
    if not EPAR_DOCS_JSON.exists():
        print(f"ERROR: EPAR documents JSON not found: {EPAR_DOCS_JSON}")
        print("Run 'python scripts/download_ema.py --json-only' first.")
        return []

    with open(EPAR_DOCS_JSON) as f:
        data = json.load(f)

    # Handle both list and dict formats
    records = data if isinstance(data, list) else data.get("data", [])

    return [Document.from_json(record) for record in records]


def match_documents_to_medicines(
    documents: list[Document],
    medicines: dict[str, Medicine]
) -> dict[str, list[Document]]:
    """Match documents to medicines by name.

    Returns dict mapping product_number to list of documents.
    """
    # Build name lookup: normalized_name -> product_number
    name_to_product = {}
    for product_num, med in medicines.items():
        normalized = normalize_name(med.name)
        if normalized:
            name_to_product[normalized] = product_num

    # Match documents
    matched: dict[str, list[Document]] = defaultdict(list)
    unmatched_count = 0

    for doc in documents:
        if not doc.medicine_name:
            unmatched_count += 1
            continue

        normalized = normalize_name(doc.medicine_name)

        # Try exact match first
        if normalized in name_to_product:
            product_num = name_to_product[normalized]
            doc.product_number = product_num
            matched[product_num].append(doc)
            continue

        # Try prefix match (for cases like "Drug Name Film-Coated Tablets")
        found = False
        for name, product_num in name_to_product.items():
            if normalized.startswith(name) or name.startswith(normalized):
                doc.product_number = product_num
                matched[product_num].append(doc)
                found = True
                break

        if not found:
            unmatched_count += 1

    print(f"Matched {len(matched)} products with documents")
    print(f"Unmatched documents: {unmatched_count}")

    return matched


def filter_qualifying_products(
    medicines: dict[str, Medicine],
    product_docs: dict[str, list[Document]]
) -> dict[str, tuple[Medicine, list[Document]]]:
    """Filter to human medicines with assessment reports.

    Returns dict mapping product_number to (medicine, documents) tuple.
    """
    qualifying = {}

    for product_num, docs in product_docs.items():
        # Check if we have this medicine
        if product_num not in medicines:
            continue

        med = medicines[product_num]

        # Filter to Human only
        if med.category != "Human":
            continue

        # Filter to Authorised only
        if med.status != "Authorised":
            continue

        # Check for at least one assessment-report
        has_assessment = any(d.doc_type == "assessment-report" for d in docs)
        if not has_assessment:
            continue

        qualifying[product_num] = (med, docs)

    return qualifying


def url_to_raw_path(url: str) -> Path:
    """Convert EMA URL to local _raw path."""
    parsed = urlparse(url)
    # www.ema.europa.eu/en/documents/assessment-report/file.pdf
    rel_path = parsed.netloc + parsed.path
    return RAW_DIR / rel_path


def escape_product_number(product_num: str) -> str:
    """Escape product number for use in directory names.

    EMEA/H/C/005824 -> EMEA-H-C-005824
    """
    return escape_for_path(product_num)


def create_files_symlinks(
    product_num: str,
    docs: list[Document],
    stats: ViewStatistics,
    dry_run: bool = False
) -> dict[str, Path]:
    """Create symlinks in files/{product}/EMA/ pointing to _raw/.

    Returns dict mapping doc URL to symlink path (for By-ATC to reference).
    """
    escaped_product = escape_product_number(product_num)
    product_dir = EMA_ACCESSION_DIR / "files" / escaped_product / "EMA"

    symlink_map = {}

    for doc in docs:
        if not doc.url:
            continue

        # Target in _raw/
        target = url_to_raw_path(doc.url)

        # Symlink path
        filename = doc.get_filename()
        link = product_dir / filename

        symlink_map[doc.url] = link

        if dry_run:
            print(f"  [DRY-RUN] Would create: {link.relative_to(DOCUMENTS_DIR)}")
            print(f"            -> {target.relative_to(RAW_DIR)}")
            stats.symlinks_created += 1
            continue

        # Create symlink (allow broken - files not downloaded yet)
        create_symlink_safe(target, link, allow_broken=True, stats=stats)

    return symlink_map


def extract_common_name(names: list[str]) -> str | None:
    """Extract common substance name from a list of product names.

    For products like:
    - "Bortezomib Sun"
    - "Bortezomib Hospira"
    - "Bortezomib Fresenius Kabi"

    Returns "Bortezomib".
    """
    if not names:
        return None

    # Find common prefix word by word
    words_list = [name.split() for name in names]
    if not words_list:
        return None

    min_len = min(len(w) for w in words_list)
    common_words = []

    for i in range(min_len):
        first_word = words_list[0][i].lower()
        if all(w[i].lower() == first_word for w in words_list):
            common_words.append(words_list[0][i])  # Keep original case from first
        else:
            break

    if common_words:
        return " ".join(common_words)

    return None


def build_atc_trie(products: dict[str, tuple[Medicine, list[Document]]]) -> dict:
    """Build a trie of products grouped by ATC code prefixes.

    Returns nested dict where:
    - Keys are ATC code segments
    - Values are either dicts (more children) or lists of (med, docs) tuples (leaf products)
    """
    from ema_atc_codes import ATC_LEVEL1, ATC_LEVEL2, ATC_LEVEL3

    def normalize_atc(code: str) -> str:
        """Pad short ATC codes with XX to indicate unspecified subclass."""
        if not code:
            return "Z00XXXX"
        # Target length is 7 (e.g., L01FF02)
        # Pad with X at appropriate positions
        if len(code) < 7:
            return code + "X" * (7 - len(code))
        return code

    # Group products by ATC code (normalized)
    by_atc: dict[str, list[tuple[Medicine, list[Document]]]] = {}
    for product_num, (med, docs) in products.items():
        atc = normalize_atc(med.atc_code or "")
        if atc not in by_atc:
            by_atc[atc] = []
        by_atc[atc].append((med, docs))

    def get_atc_name(code: str) -> str:
        """Get name for an ATC code."""
        # First try exact match or progressively shorter prefixes
        # Check LEVEL3 (4-5+ char codes like L01X, L01XG, L01XG01)
        for length in [len(code), 5, 4]:
            prefix = code[:length] if len(code) >= length else code
            if prefix in ATC_LEVEL3:
                return ATC_LEVEL3[prefix]

        # Strip trailing X's and try again (X indicates unspecified subclass)
        base_code = code.rstrip('X')
        for length in [len(base_code), 5, 4]:
            prefix = base_code[:length] if len(base_code) >= length else base_code
            if prefix in ATC_LEVEL3:
                return ATC_LEVEL3[prefix]

        # Check LEVEL2 (3-char codes like L01, J05)
        if len(base_code) >= 3 and base_code[:3] in ATC_LEVEL2:
            return ATC_LEVEL2[base_code[:3]]

        # Check LEVEL1 (1-char codes like L, J)
        if len(base_code) >= 1 and base_code[0] in ATC_LEVEL1:
            return ATC_LEVEL1[base_code[0]]

        return "Unknown"

    def get_collapsed_prefix(code: str, length: int) -> str:
        """Get collapsed prefix for a code at given length.

        Collapses trailing X's to single X (e.g., L01XX -> L01X).
        """
        if length == 0:
            return ""
        prefix = code[:length] if len(code) >= length else code
        base = prefix.rstrip('X')
        if len(base) < len(prefix):
            return base + 'X' if base else 'X'
        return prefix

    def get_next_meaningful_level(code: str, current_len: int) -> int:
        """Find next level that produces a different collapsed prefix.

        Skips levels where X-padding would create identical collapsed prefixes.
        """
        levels = [1, 3, 4, 5, 7]
        current_collapsed = get_collapsed_prefix(code, current_len)

        for level in levels:
            if level > current_len:
                next_collapsed = get_collapsed_prefix(code, level)
                if next_collapsed != current_collapsed:
                    return level
        # No more meaningful levels - return beyond max to signal leaf
        return 999

    def build_level(codes_products: dict[str, list], prefix_len: int, parent_prefix: str = "") -> dict:
        """Recursively build trie level.

        Args:
            codes_products: dict mapping ATC code to list of (med, docs)
            prefix_len: current prefix length to group by
            parent_prefix: the collapsed prefix of the parent level (to avoid duplicates)
        """
        if not codes_products:
            return {}

        # Group by collapsed prefix of given length
        groups: dict[str, dict[str, list]] = {}
        for code, prods in codes_products.items():
            prefix = get_collapsed_prefix(code, prefix_len)
            if prefix not in groups:
                groups[prefix] = {}
            groups[prefix][code] = prods

        result = {}
        for prefix, sub_codes in groups.items():
            # Skip if this prefix is same as parent (would create duplicate folder)
            if prefix and prefix == parent_prefix:
                # Don't create folder, just recurse with higher level
                first_code = next(iter(sub_codes.keys()))
                next_level = get_next_meaningful_level(first_code, prefix_len)
                if next_level >= 999:
                    # Output as leaves
                    for code, prods in sub_codes.items():
                        for med, docs in prods:
                            escaped = escape_product_number(med.product_number)
                            atc = normalize_atc(med.atc_code or "")
                            display_name = f"{atc}) {med.name} - {escaped}"
                            fs_name = f"{atc}) {escape_for_path(med.name)} - {escaped}"
                            result[fs_name] = ("leaf", med, docs, display_name)
                else:
                    # Recurse but keep same parent_prefix
                    children = build_level(sub_codes, next_level, parent_prefix)
                    result.update(children)
                continue

            # Count total products in this group
            total_products = sum(len(prods) for prods in sub_codes.values())

            # If only one product, it's a leaf - don't create subdirectory
            if total_products == 1:
                # Get the single product
                for code, prods in sub_codes.items():
                    for med, docs in prods:
                        # Leaf node: key is product folder name
                        escaped = escape_product_number(med.product_number)
                        atc = normalize_atc(med.atc_code or "")
                        display_name = f"{atc}) {med.name} - {escaped}"
                        fs_name = f"{atc}) {escape_for_path(med.name)} - {escaped}"
                        result[fs_name] = ("leaf", med, docs, display_name)

            # If multiple products but they all have same code (no further splitting possible)
            elif len(sub_codes) == 1:
                code = list(sub_codes.keys())[0]
                prods = sub_codes[code]

                # Find next level that would produce a different prefix
                next_level = get_next_meaningful_level(code, prefix_len)

                if next_level >= 999 or len(code) <= prefix_len:
                    # No more meaningful splits by ATC prefix
                    if len(prods) > 1:
                        # Multiple products with same full ATC code - create subdirectory
                        # for the chemical substance
                        atc = normalize_atc(code)
                        # Try to get substance name from ATC dictionary, or extract from product names
                        substance_name = get_atc_name(atc)
                        # If name is generic (same as parent level), extract common name from products
                        parent_name = get_atc_name(atc[:5]) if len(atc) >= 5 else ""
                        if substance_name == parent_name:
                            # Extract common prefix from medicine names
                            names = [med.name for med, _ in prods]
                            common = extract_common_name(names)
                            if common:
                                substance_name = common
                        display_folder = f"{atc}) {substance_name}"
                        fs_folder = f"{atc}) {escape_for_path(substance_name)}"
                        children = {}
                        for med, docs in prods:
                            escaped = escape_product_number(med.product_number)
                            # Simpler leaf name since ATC is in parent folder
                            display_leaf = f"{med.name} - {escaped}"
                            fs_leaf = f"{escape_for_path(med.name)} - {escaped}"
                            children[fs_leaf] = ("leaf", med, docs, display_leaf)
                        result[fs_folder] = ("dir", children, display_folder)
                    else:
                        # Single product - output as leaf
                        for med, docs in prods:
                            escaped = escape_product_number(med.product_number)
                            atc = normalize_atc(med.atc_code or "")
                            display_name = f"{atc}) {med.name} - {escaped}"
                            fs_name = f"{atc}) {escape_for_path(med.name)} - {escaped}"
                            result[fs_name] = ("leaf", med, docs, display_name)
                else:
                    children = build_level(sub_codes, next_level, prefix)
                    if len(children) == 1:
                        # Single child - don't create intermediate directory
                        result.update(children)
                    else:
                        # Multiple children - create subdirectory
                        name = get_atc_name(prefix)
                        folder_name = f"{prefix}) {escape_for_path(name)}"
                        display_name = f"{prefix}) {name}"
                        result[folder_name] = ("dir", children, display_name)

            else:
                # Multiple different codes - need to split
                # Find next level - use first code to determine progression
                # (all codes in group share the prefix, so progression is same)
                first_code = next(iter(sub_codes.keys()))
                next_level = get_next_meaningful_level(first_code, prefix_len)

                # If no meaningful next level, output leaves (or group by full ATC)
                if next_level >= 999:
                    for code, prods in sub_codes.items():
                        if len(prods) > 1:
                            # Multiple products with same full ATC code - create subdirectory
                            atc = normalize_atc(code)
                            # Try to get substance name from ATC dictionary, or extract from product names
                            substance_name = get_atc_name(atc)
                            parent_name = get_atc_name(atc[:5]) if len(atc) >= 5 else ""
                            if substance_name == parent_name:
                                names = [med.name for med, _ in prods]
                                common = extract_common_name(names)
                                if common:
                                    substance_name = common
                            display_folder = f"{atc}) {substance_name}"
                            fs_folder = f"{atc}) {escape_for_path(substance_name)}"
                            children = {}
                            for med, docs in prods:
                                escaped = escape_product_number(med.product_number)
                                display_leaf = f"{med.name} - {escaped}"
                                fs_leaf = f"{escape_for_path(med.name)} - {escaped}"
                                children[fs_leaf] = ("leaf", med, docs, display_leaf)
                            result[fs_folder] = ("dir", children, display_folder)
                        else:
                            # Single product - output as leaf
                            for med, docs in prods:
                                escaped = escape_product_number(med.product_number)
                                atc = normalize_atc(med.atc_code or "")
                                display_name = f"{atc}) {med.name} - {escaped}"
                                fs_name = f"{atc}) {escape_for_path(med.name)} - {escaped}"
                                result[fs_name] = ("leaf", med, docs, display_name)
                    continue

                children = build_level(sub_codes, next_level, prefix)

                if prefix_len == 0:
                    # Top level - don't create a folder, just return children
                    result.update(children)
                elif len(children) == 1:
                    # Single child after recursion - collapse
                    result.update(children)
                else:
                    # Multiple children - create subdirectory for this prefix
                    name = get_atc_name(prefix)
                    folder_name = f"{prefix}) {escape_for_path(name)}"
                    display_name = f"{prefix}) {name}"
                    result[folder_name] = ("dir", children, display_name)

        return result

    return build_level(by_atc, 0)


def create_atc_view(
    products: dict[str, tuple[Medicine, list[Document]]],
    all_files_symlinks: dict[str, dict[str, Path]],
    stats: ViewStatistics,
    dry_run: bool = False
):
    """Create the By-ATC view with collapsed single-child nodes."""

    # Build the trie
    trie = build_atc_trie(products)

    def write_display_metadata(dir_path: Path, display_name: str, fs_name: str):
        """Write __metadata.json if display name differs from filesystem name."""
        if display_name != fs_name:
            metadata_path = dir_path / "__metadata.json"
            metadata = {"_folder": {"title": display_name}}
            dir_path.mkdir(parents=True, exist_ok=True)
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

    def create_from_trie(node: dict, base_path: Path):
        """Recursively create directories and symlinks from trie."""
        for fs_name, value in sorted(node.items()):
            if value[0] == "leaf":
                # Leaf node - create product directory with symlinks
                # value = ("leaf", med, docs, display_name)
                _, med, docs, display_name = value
                product_dir = base_path / fs_name
                files_symlinks = all_files_symlinks.get(med.product_number, {})

                # Write metadata if display name differs
                if not dry_run:
                    write_display_metadata(product_dir, display_name, fs_name)

                for doc in docs:
                    if not doc.url or doc.url not in files_symlinks:
                        continue

                    target = files_symlinks[doc.url]
                    link = product_dir / target.name

                    if dry_run:
                        print(f"  [DRY-RUN] ATC: {link.relative_to(DOCUMENTS_DIR)}")
                        stats.symlinks_created += 1
                        continue

                    create_symlink_safe(target, link, allow_broken=True, stats=stats)

            elif value[0] == "dir":
                # Directory node - recurse
                # value = ("dir", children, display_name)
                _, children, display_name = value
                subdir = base_path / fs_name

                # Write metadata if display name differs
                if not dry_run:
                    write_display_metadata(subdir, display_name, fs_name)

                create_from_trie(children, subdir)

    atc_base = EMA_ACCESSION_DIR / "By-ATC"
    create_from_trie(trie, atc_base)


def create_metadata(
    products: dict[str, tuple[Medicine, list[Document]]],
    stats: ViewStatistics
):
    """Create metadata.json for the accession."""
    total_docs = sum(len(docs) for _, docs in products.values())

    metadata = {
        "accession": EMA_ACCESSION,
        "title": "EMA Public Documents",
        "description": "Public assessment reports and other documents for human medicines authorized by the European Medicines Agency.",
        "drug": "Multiple (EMA database)",
        "source": "https://www.ema.europa.eu/en/medicines",
        "license": {
            "name": "EMA Public",
            "url": "https://www.ema.europa.eu/en/about-us/legal-notice"
        },
        "created": datetime.now().isoformat(),
        "stats": {
            "products": len(products),
            "documents": total_docs,
            "symlinks_created": stats.symlinks_created,
        }
    }

    metadata_path = EMA_ACCESSION_DIR / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Created: {metadata_path.relative_to(DOCUMENTS_DIR)}")


def build_ema(clean: bool = False, dry_run: bool = False):
    """Build the EMA accession structure."""
    print("=" * 60)
    print("EMA Accession Build")
    print("=" * 60)
    print(f"Accession: {EMA_ACCESSION}")
    print(f"Output: {EMA_ACCESSION_DIR}")
    print()

    # Clean if requested
    if clean and EMA_ACCESSION_DIR.exists():
        if dry_run:
            print(f"[DRY-RUN] Would remove: {EMA_ACCESSION_DIR}")
        else:
            print(f"Cleaning: {EMA_ACCESSION_DIR}")
            shutil.rmtree(EMA_ACCESSION_DIR)
        print()

    # Load data
    print("Loading EMA data...")
    medicines = load_medicines()
    if not medicines:
        return False
    print(f"  Loaded {len(medicines)} medicines")

    documents = load_documents()
    if not documents:
        return False
    print(f"  Loaded {len(documents)} documents")
    print()

    # Match documents to medicines
    print("Matching documents to medicines...")
    product_docs = match_documents_to_medicines(documents, medicines)
    print()

    # Filter qualifying products
    print("Filtering to Human + Authorised + has assessment-report...")
    qualifying = filter_qualifying_products(medicines, product_docs)
    print(f"  Qualifying products: {len(qualifying)}")
    print()

    # Create directory structure
    if not dry_run:
        EMA_ACCESSION_DIR.mkdir(parents=True, exist_ok=True)

    stats = ViewStatistics()

    # First pass: create files/ symlinks for all products
    print("Creating files/ symlinks...")
    all_files_symlinks: dict[str, dict[str, Path]] = {}
    for i, (product_num, (med, docs)) in enumerate(qualifying.items(), 1):
        if i % 100 == 0:
            print(f"  Processing {i}/{len(qualifying)}...")

        files_symlinks = create_files_symlinks(product_num, docs, stats, dry_run)
        all_files_symlinks[product_num] = files_symlinks

    print()

    # Second pass: create By-ATC/ view with collapsed hierarchy
    print("Creating By-ATC/ view...")
    create_atc_view(qualifying, all_files_symlinks, stats, dry_run)

    print()

    # Create metadata
    if not dry_run:
        create_metadata(qualifying, stats)

    # Print summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Products: {len(qualifying)}")
    print(stats)

    if stats.errors:
        print()
        print("Errors:")
        for err in stats.errors[:10]:  # Show first 10
            print(f"  {err}")
        if len(stats.errors) > 10:
            print(f"  ... and {len(stats.errors) - 10} more")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Build EMA accession structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove and rebuild the accession directory"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without making changes"
    )

    args = parser.parse_args()

    success = build_ema(clean=args.clean, dry_run=args.dry_run)
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
