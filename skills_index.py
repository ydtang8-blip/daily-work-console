from __future__ import annotations

import re
import time
from pathlib import Path

DEFAULT_SKILLS_PATH = r"C:\Users\43886\global\skills"

_cache: dict = {"t": 0.0, "skills": [], "core_names": set(), "path": ""}


def parse_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    fm = text[4:end]
    name = ""
    description = ""
    lines = fm.splitlines()
    i = 0
    in_desc = False
    desc_lines = []
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if in_desc:
            if line.startswith(("-", "name:", "description:", "other:", "version:", "license:", "created:", "homepage:", "tags:", "metadata:")):
                in_desc = False
            else:
                desc_lines.append(line.lstrip())
                i += 1
                continue
        m = re.match(r"^\s*name\s*:\s*(.+?)\s*$", line)
        if m:
            name = m.group(1).strip().strip("'\"")
            i += 1
            continue
        m = re.match(r"^\s*description\s*:\s*(.*?)\s*$", line)
        if m:
            rest = m.group(1).strip()
            if rest.startswith(">") or rest in ("|", ">"):
                in_desc = True
            elif rest:
                description = rest.strip("'\"")
            i += 1
            continue
        i += 1
    if in_desc:
        description = " ".join(desc_lines).strip()
    return {"name": name or skill_md.parent.name, "description": description}


def _core_names(skills_root: Path) -> set:
    core_md = skills_root / "core.md"
    names = set()
    if not core_md.exists():
        return names
    for line in core_md.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^\s*[-*]\s+([\w-]+)\s*—", line)
        if m:
            names.add(m.group(1))
    return names


def scan(path: str = "") -> list[dict]:
    root = Path(path or DEFAULT_SKILLS_PATH).expanduser()
    now = time.time()
    if _cache["skills"] and _cache["path"] == str(root) and now - _cache["t"] < 60:
        return _cache["skills"]
    skills = []
    if root.exists():
        core_names = _core_names(root)
        for child in sorted(root.iterdir()):
            if not child.is_dir() or child.name == "library":
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue
            fm = parse_frontmatter(skill_md)
            loc = "core" if fm.get("name") in core_names else "top"
            skills.append(
                {
                    "name": fm.get("name") or child.name,
                    "description": fm.get("description", ""),
                    "location": loc,
                    "path": str(skill_md),
                }
            )
        lib_root = root / "library"
        if lib_root.is_dir():
            for sub in sorted(lib_root.iterdir()):
                sm = sub / "SKILL.md"
                if sm.exists():
                    fm = parse_frontmatter(sm)
                    skills.append(
                        {
                            "name": fm.get("name") or sub.name,
                            "description": fm.get("description", ""),
                            "location": "library",
                            "path": str(sm),
                        }
                    )
        skills.sort(key=lambda s: s["name"])
    _cache["skills"] = skills
    _cache["path"] = str(root)
    _cache["t"] = now
    return skills


def search(q: str = "", path: str = "") -> list[dict]:
    skills = scan(path)
    q = q.strip().lower()
    if not q:
        return skills
    out = []
    for s in skills:
        hay = (s["name"] + " " + s["description"] + " " + s["path"]).lower()
        if all(part in hay for part in q.split()):
            out.append(s)
    return out


def counts(path: str = "") -> dict:
    skills = scan(path)
    c = {"core": 0, "top": 0, "library": 0, "total": len(skills)}
    for s in skills:
        c[s["location"]] = c.get(s["location"], 0) + 1
    return c
