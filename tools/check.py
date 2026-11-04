#!/usr/bin/env python3
"""Verify source coverage, identities, provenance, links and safe re-ingestion."""
import hashlib, shutil, subprocess, sys, tempfile, uuid, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import ingest

def digest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '__pycache__' not in str(p)}

def main():
    from render_readme import render_readme
    render_readme(ROOT, check=True)
    entries = ingest.parse_list(ROOT / 'raw/2026-11-04/README.md')
    grouped = {}
    for e in entries: grouped.setdefault(ingest.normalise(e['url']), []).append(e)
    pages, ids = {}, set()
    for p in (ROOT / 'wiki').glob('*.md'):
        f, body = ingest.split(p.read_text())
        if f.get('type') == 'index':
            assert len(body)//4 <= 4000, p
            continue
        assert f['type'] == 'entity'
        assert f['uid'] not in ids
        uuid.UUID(f['uid']); ids.add(f['uid'])
        assert 0 < len(f['summary']) <= 160
        assert f['depth'] in {'stub','brief','full','deep'}
        assert len(body)//4 <= {'stub':750,'brief':750,'full':2500,'deep':6000}[f['depth']]
        assert f['status'] == 'unknown' and 'last_checked' not in f
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', f['created'])
        assert f['source_commit'] in f['sources'][0]['url']
        key = ingest.normalise(f['url'])
        assert key not in pages
        pages[key] = p, f
    assert len(pages) == len(grouped)
    for key, rows in grouped.items():
        assert pages[key][1]['list_entries'] == rows, key
    visited, pending = set(), [ROOT / 'index.md']
    while pending:
        p = pending.pop().resolve()
        if p in visited: continue
        visited.add(p)
        for target in re.findall(r'\]\(([^)]+)\)', ingest.split(p.read_text())[1]):
            if '://' in target or target.startswith('#'): continue
            target = (p.parent / target.split('#')[0]).resolve()
            assert target.is_relative_to(ROOT.resolve()) and target.exists(), target
            if target.suffix == '.md': pending.append(target)
    assert all(p.resolve() in visited for p, _ in pages.values())
    for line in (ROOT/'raw/MANIFEST.sha256').read_text().splitlines():
        expected, name = line.split('  ',1)
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)/'kb'
        shutil.copytree(ROOT,work,ignore=shutil.ignore_patterns('__pycache__','.git'))
        command = [sys.executable,str(work/'tools/ingest.py'),'--date','2026-11-04']
        before = digest(work)
        subprocess.run(command,check=True)
        assert before == digest(work), 're-ingestion changed files'
        source = work/'raw/2026-11-04/README.md'
        original_source = source.read_text()
        first = entries[0]
        path, original = pages[ingest.normalise(first['url'])]
        page = work/path.relative_to(ROOT)
        for depth in ('brief','full','deep'):
            fields = dict(original); fields['depth'] = depth
            marker = '\nAuthored content must survive.\n'
            page.write_text(ingest.dump(fields, marker))
            source.write_text(original_source.replace(first['description'], first['description']+' Updated.',1))
            subprocess.run(command,check=True)
            f,body = ingest.split(page.read_text())
            assert body == marker and f['depth'] == depth
            assert f['uid'] == original['uid'] and f['created'] == original['created']
    print(f'PASS: {len(entries)} source rows, {len(pages)} unique resources; coverage, UUIDs, provenance, links, checksums, idempotency, authored-depth preservation')
if __name__ == '__main__': main()

