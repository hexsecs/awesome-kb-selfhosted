# Selfhosted (Awesome KB)

Resource knowledge base ingested from awesome-selfhosted/awesome-selfhosted, preserving the canonical list's categories and descriptions.

Browse [the index](index.md). These are unverified stub entries, captured from the [canonical upstream list](https://github.com/awesome-selfhosted/awesome-selfhosted/blob/ebc8cb0883fcf5cf061245db9398b9a93fd6628a/README.md) on 2026-11-04. No linked resources were recursively fetched.

## Update and validate

```sh
python -m pip install 'git+https://github.com/OpenNorms/openshelf.git'
python tools/check.py
openshelf lint .
python tools/ingest.py --date 2026-11-04
```

Default ingestion uses the pinned raw snapshot. To update, capture a reviewed upstream README and commit in a new dated directory with `capture.json`, retain its notices, update raw checksums, then run `python tools/ingest.py --source raw/YYYY-MM-DD --date YYYY-MM-DD`. Existing UUIDs and creation dates are preserved. Authored brief/full/deep bodies survive updates; removed resources are retained as historical records.

Content license: **CC-BY-SA-3.0**. See [third-party notices](THIRD_PARTY_NOTICES.md) and [license](LICENSE).
