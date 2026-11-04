# OpenShelf contributor instructions

Use OpenShelf 1.7 with the awesome profile and the layout in kb.yaml. Keep stable UUIDs and creation dates. Entity summaries are at most 160 characters. Stub and brief bodies fit 750 tokens; full 2500; deep 6000. Indexes fit 4000 tokens.

Keep unverified imports at depth stub and status unknown. Add last_checked only after a real resource check. Preserve raw immutable snapshots, checksum manifest, attribution, license notices and source revisions. Never recursively ingest linked resources as part of list import.

Run python tools/check.py and openshelf lint . before merging. Update log.md for substantive changes. Do not overwrite authored brief/full/deep page bodies with generated stubs.
