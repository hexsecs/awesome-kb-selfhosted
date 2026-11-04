# OpenShelf contributor instructions

Use OpenShelf 1.7 with the awesome profile and the layout in kb.yaml. Keep stable UUIDs and creation dates. Entity summaries are at most 160 characters. Stub and brief bodies fit 750 tokens; full 2500; deep 6000. Indexes fit 4000 tokens.

Keep unverified imports at depth stub and status unknown. Add last_checked only after a real resource check. Preserve raw immutable snapshots, checksum manifest, attribution, license notices and source revisions. Never recursively ingest linked resources as part of list import.

Run python tools/check.py and openshelf lint . before merging. Update log.md for substantive changes. Do not overwrite authored brief/full/deep page bodies with generated stubs.

## Generated README list

The README contains a marked generated list, maintained by tools/render_readme.py
from the same index graph. Ingest updates both views; do not edit between the
generated markers. Introduction and license sections outside the markers stay
manual. Entry names link to KB pages and upstream links open original resources.
Large catalogs continue under lists/ at category boundaries to keep README and
continuation pages below GitHub's 500 KiB display limit. These files are generated,
not additional OpenShelf entities. Run python3 tools/render_readme.py --check to
verify completeness, links, display size and synchronization.
