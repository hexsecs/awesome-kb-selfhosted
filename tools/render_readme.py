#!/usr/bin/env python3
"""Generate a traditional list view from the OpenShelf navigation graph."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

BEGIN = "<!-- BEGIN GENERATED AWESOME LIST -->"
END = "<!-- END GENERATED AWESOME LIST -->"
LIMIT = 480 * 1024
LINK = re.compile(r"^- \[.*\]\(([^)]+\.md)(?:#[^)]*)?\)")


def metadata(page: Path) -> dict:
    text = page.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    block = text[4:].split("\n---\n", 1)[0]
    return yaml.load(block, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader)) or {}


def label(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def collect(root: Path) -> list[tuple[str, list[tuple[Path, dict]]]]:
    """Follow the index order, keeping repeated category memberships."""
    manifest = yaml.load((root / "kb.yaml").read_text(), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    layout = manifest.get("layout", {})
    entry = root / layout.get("index", "index.md")
    pages = root / layout.get("pages", "wiki")
    groups = []
    ancestors = set()

    def walk(path: Path, category: str | None = None):
        path = path.resolve()
        if path in ancestors:
            raise ValueError(f"Index cycle: {path}")
        ancestors.add(path)
        text = path.read_text(encoding="utf-8")
        fields = metadata(path)
        heading = next((line[2:] for line in text.splitlines()
                        if line.startswith("# ")), path.stem)
        items = []

        def flush():
            if items:
                groups.append((category or heading, list(items)))
                items.clear()

        for line in text.splitlines():
            match = LINK.match(line)
            if not match:
                continue
            target = (path.parent / match[1]).resolve()
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError(f"Invalid index target: {target}")
            data = metadata(target)
            if data.get("type") == "entity":
                if not data.get("url"):
                    raise ValueError(f"Missing resource URL: {target}")
                items.append((target, data))
            elif data.get("type") == "index" or not data:
                flush()
                walk(target, data.get("title") or next(
                    (line[2:] for line in target.read_text().splitlines()
                     if line.startswith("# ")), target.stem))
        flush()
        ancestors.remove(path)

    walk(entry)
    reachable = {p for _, items in groups for p, _ in items}
    expected = {p.resolve() for p in pages.rglob("*.md")
                if metadata(p).get("type") == "entity"}
    if reachable != expected:
        raise ValueError(f"README entity coverage mismatch: {len(reachable)} / {len(expected)}")
    return groups


def row(root: Path, page: Path, fields: dict, prefix="") -> str:
    title = label(fields["title"])
    description = str(fields.get("list_summary") or fields["summary"])
    # Descriptions can carry Markdown whose links are relative to upstream.
    # The KB page keeps full source wording; the list view uses safe plain text.
    description = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", description)
    description = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", description)
    description = re.sub(r"<[^>]*>", "", description)
    description = re.sub(r"\s+", " ", description).strip()
    description = label(description)
    target = prefix + page.relative_to(root.resolve()).as_posix()
    url = str(fields["url"]).replace("<", "%3C").replace(">", "%3E")
    return f"- [{title}]({target}) · [upstream](<{url}>) — {description}\n"


def category_block(root, number, title, items, prefix=""):
    return (f'<a id="list-category-{number}"></a>\n\n### {label(title)}\n\n'
            + "".join(row(root, p, f, prefix) for p, f in items) + "\n")


def manual_parts(text: str) -> tuple[str, str]:
    if BEGIN in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise ValueError("README must contain exactly one generated region")
        before, rest = text.split(BEGIN, 1)
        _, after = rest.split(END, 1)
        return before, after
    # Put the list after the introduction and before maintenance/license sections.
    boundary = re.search(r"(?m)^## ", text)
    pos = boundary.start() if boundary else len(text)
    return text[:pos].rstrip() + "\n\n", "\n\n" + text[pos:].lstrip()


def expected_files(root: Path) -> dict[Path, str]:
    root = root.resolve()
    original = (root / "README.md").read_text(encoding="utf-8")
    before, after = manual_parts(original)
    groups = collect(root)
    blocks = [category_block(root, n, title, items)
              for n, (title, items) in enumerate(groups, 1)]
    # Reserve space for every category's contents link and original manual text.
    reserve = len((before + after).encode()) + sum(
        len(title.encode()) + 140 for title, _ in groups) + 4096
    chunks, chunk, used = [], [], reserve
    for i, block in enumerate(blocks):
        size = len(block.encode())
        if size + reserve > LIMIT:
            raise ValueError(f"Category too large for README paging: {groups[i][0]}")
        if chunk and used + size > LIMIT:
            chunks.append(chunk)
            chunk, used = [], reserve
        chunk.append(i)
        used += size
    if chunk:
        chunks.append(chunk)
    location = {i: part for part, indexes in enumerate(chunks) for i in indexes}
    lines = ["## Resource list", "",
             "Generated from the OpenShelf index. Entry names open KB pages; "
             "**upstream** opens the original resource.", ""]
    if len(chunks) > 1:
        lines += ["This list continues across linked pages to stay below GitHub's "
                  "README display limit. Every category is linked below.", ""]
    lines += ["### Contents", ""]
    for i, (title, _) in enumerate(groups):
        part = location[i]
        target = ("" if part == 0 else f"lists/list-{part + 1}.md") + f"#list-category-{i + 1}"
        lines.append(f"- [{label(title)}]({target})")
    lines += [""]
    generated = "\n".join(lines) + "\n"
    generated += "".join(blocks[i] for i in chunks[0])
    if len(chunks) > 1:
        generated += "[Continue the list →](lists/list-2.md)\n\n"
    outputs = {root / "README.md": before + BEGIN + "\n\n" + generated + END + after}
    for part in range(1, len(chunks)):
        body = f"# Resource list — part {part + 1}\n\n"
        body += "[README and full contents](../README.md#resource-list)"
        if part > 1:
            body += f" · [Previous](list-{part}.md)"
        if part + 1 < len(chunks):
            body += f" · [Next](list-{part + 2}.md)"
        body += "\n\n"
        for i in chunks[part]:
            title, items = groups[i]
            body += category_block(root, i + 1, title, items, "../")
        outputs[root / f"lists/list-{part + 1}.md"] = body
    for path, text in outputs.items():
        if len(text.encode("utf-8")) >= 500 * 1024:
            raise ValueError(f"Generated list would be truncated on GitHub: {path}")
        for target in re.findall(r"(?<!\\)\]\(([^)]+)\)", text):
            if "://" in target or target.startswith(("#", "<")):
                continue
            local = (path.parent / unquote(target.split("#", 1)[0])).resolve()
            if local not in outputs and not local.exists():
                raise ValueError(f"Broken README link: {path}: {target}")
    return outputs


def render_readme(root: Path, check=False):
    outputs = expected_files(root)
    existing = set((root / "lists").glob("list-*.md"))
    if check:
        for path, content in outputs.items():
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise ValueError(f"Generated README list is stale: {path}")
        if existing - outputs.keys():
            raise ValueError("Stale list continuation pages")
    else:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                path.write_text(content, encoding="utf-8")
        for path in existing - outputs.keys():
            path.unlink()
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    files = render_readme(root, args.check)
    print(f"README list: {len(files)} page(s), {sum(len(s.encode()) for s in files.values()):,} bytes")
