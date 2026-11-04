#!/usr/bin/env python3
"""Import the captured canonical list. Preserve UUIDs and authored page depth."""
from pathlib import Path
from collections import defaultdict
import argparse, hashlib, json, re, secrets, subprocess, time, uuid
import yaml
ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "ingest.json").read_text())

def mint_uid() -> str:
    """A fresh UUIDv7, the form OpenShelf SPEC section 4.1 recommends."""
    if hasattr(uuid, "uuid7"):
        return str(uuid.uuid7())
    ms = int(time.time() * 1000) & ((1 << 48) - 1)
    value = (ms << 80) | (0x7 << 76) | (secrets.randbits(12) << 64) \
        | (0b10 << 62) | secrets.randbits(62)
    return str(uuid.UUID(int=value))



def normalise(url):
    return re.sub(r"^https?://", "", url).rstrip("/").lower()

def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "entry"

def clean(text):
    text = re.sub(r"\[!\[[^\]]*\]\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"!\[[^\]]*\]\[[^\]]*\]", "", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\]\([^)]*\)", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip(" -")

def short(text):
    text = clean(text)
    return text if len(text) <= 160 else text[:157].rsplit(" ", 1)[0].rstrip(",;:") + "…"

def first_link(text):
    m = re.match(r"^\[([^\]]+)\]\(", text)
    if not m:
        return None
    begin = m.end()
    depth, i = 1, begin
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return m.group(1), text[begin:i], text[i+1:].strip()
        i += 1
    raise ValueError("Unclosed resource URL: " + text)

def parse_list(path):
    entries, heads, in_code = [], {}, False
    for line in path.read_text().splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        hm = re.match(r"^(#{2,6}) (.+)", line)
        if hm:
            level = len(hm.group(1))
            heads = {k: v for k, v in heads.items() if k < level}
            heads[level] = clean(hm.group(2))
            continue
        top = heads.get(2, "")
        if CONFIG["kind"] == "selfhosted" and top != "Software":
            continue
        if CONFIG["kind"] == "mac" and (not top or top in {"Contents", "Contributors", "License"}):
            continue
        if CONFIG["kind"] == "mac" and heads.get(3) == "Pirated software download site blocklist":
            continue
        bm = re.match(r"^\s*[-*] (.+)", line)
        if not bm:
            continue
        text = bm.group(1)
        found = first_link(text)
        if found:
            title, url, rest = found
            if not url.startswith(("http://", "https://")):
                continue
            # A primary resource bullet, not a contents link or return control.
            rest = re.sub(r"^`[^\`]*`\s*", "", rest)
            description = re.sub(r"^[-–—]\s*", "", rest).strip()
            if not description:
                description = title + " — resource listed in " + top + "."
            category = " / ".join(heads[k] for k in sorted(heads) if k >= (3 if CONFIG["kind"] == "selfhosted" else 2))
            entries.append(dict(title=title, url=url, category=category or top, description=description))
        elif CONFIG["kind"] == "mac" and top == "Mac App Download Sites":
            # Two named download-site rows use Name:[URL](URL), not [Name](URL).
            special = re.match(r"^([^：:]+)[：:]\[https?://[^]]+\]\((https?://[^)]+)\)", text)
            if special:
                title, url = special.groups()
                category = " / ".join(heads[k] for k in sorted(heads))
                entries.append(dict(title=title, url=url, category=category, description=title + " — Mac app download site listed by the source."))
    if not entries:
        raise ValueError("No resource entries; refusing empty import")
    return entries

def split(text):
    if not text.startswith("---\n"):
        return {}, text
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm), body

def dump(fields, body):
    return "---\n" + json.dumps(fields, ensure_ascii=False, indent=2) + "\n---\n" + body

def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and "__pycache__" not in str(p)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=ROOT / "raw/2026-11-04")
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d", time.gmtime()))
    args = ap.parse_args()
    capture = json.loads((args.source / "capture.json").read_text()) if (args.source / "capture.json").exists() else {}
    commit = capture.get("source_commit")
    if not commit:
        commit = subprocess.run(["git", "-C", str(args.source), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    entries = parse_list(args.source / "README.md")
    grouped = {}
    for entry in entries:
        grouped.setdefault(normalise(entry["url"]), []).append(entry)
    wiki = ROOT / "wiki"
    wiki.mkdir(exist_ok=True)
    before = snapshot(ROOT)
    existing = {}
    taken = set()
    for p in wiki.glob("*.md"):
        f, body = split(p.read_text())
        taken.add(p.stem)
        if f.get("type") == "entity":
            existing[normalise(f["url"])] = (p, f, body)
    sections = defaultdict(list)
    for key, rows in grouped.items():
        e = rows[0]
        old = existing.get(key)
        if old:
            p, fields, body = old
        else:
            name, n = slug(e["title"]), 2
            stem = name
            while stem in taken:
                stem, n = name + "-" + str(n), n + 1
            taken.add(stem)
            p, fields, body = wiki / (stem + ".md"), {}, ""
        changed = fields.get("list_entries") != rows
        fields.update(title=e["title"], summary=short(e["description"]), type="entity",
                      category=e["category"], url=e["url"], list_summary=e["description"],
                      list_entries=rows)
        fields.setdefault("uid", mint_uid())
        fields.setdefault("created", args.date)
        fields.setdefault("depth", "stub")
        fields.setdefault("status", "unknown")
        if changed:
            fields["updated"] = args.date
            fields["source_list"] = CONFIG["source"]
            fields["source_commit"] = commit
        fields.setdefault("sources", [{"url": CONFIG["source_url"] + "/blob/" + commit + "/README.md", "retrieved": args.date}])
        if fields["depth"] == "stub":
            body = "\n" + clean(e["description"]) + "\n\n" + "- **Resource:** " + e["url"] + "\n- **Source:** [" + CONFIG["source"] + "](" + CONFIG["source_url"] + "/blob/" + commit + "/README.md)\n\nGenerated stub; resource status has not been independently checked.\n"
            if len(rows) > 1:
                body += "\nListed under: " + "; ".join(dict.fromkeys(r["category"] for r in rows)) + ".\n"
        p.write_text(dump(fields, body))
        for row in rows:
            sections[row["category"]].append((p.stem, row["title"], short(row["description"])))
    for key, (p, fields, body) in existing.items():
        if key not in grouped:
            fields["status"] = "archived"
            if "Delisted from the source list" not in body:
                body += "\n> Delisted from the source list; retained as a historical record.\n"
            p.write_text(dump(fields, body))
            sections[fields["category"]].append((p.stem, fields["title"] + " (delisted)", fields["summary"]))
    index = ["# " + CONFIG["title"], "", CONFIG["description"], "", "## Categories", ""]
    for category, items in sections.items():
        name = "index-" + slug(category)
        out = ["---", "type: index", "title: " + json.dumps(category), "---", "", "# " + category, ""]
        out.extend("- [" + title + "](" + stem + ".md) — " + summary for stem, title, summary in items)
        (wiki / (name + ".md")).write_text("\n".join(out) + "\n")
        index.append("- [" + category + "](wiki/" + name + ".md) — " + str(len(items)) + " entries")
    (ROOT / "index.md").write_text("\n".join(index) + "\n")
    after = snapshot(ROOT)
    print(str(len(entries)) + " source rows; " + str(len(grouped)) + " unique resources; " + str(sum(before.get(k) != v for k, v in after.items())) + " files changed")

if __name__ == "__main__":
    main()
