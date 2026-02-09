#!/usr/bin/env python3
"""Generate a comprehensive git repository statistics report.

Produces a Markdown report with Unicode charts covering commits,
contributors, activity patterns, code stats, churn, and more.

Usage:
    python scripts/git_report.py
    python scripts/git_report.py --repo /path/to/repo
    python scripts/git_report.py --output my_report.md
    python scripts/git_report.py --top-n 30
"""

import argparse
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

COMMIT_DELIM = "---GIT_REPORT_DELIM---"
BLOCK_CHARS = " ░▒▓█"
SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"
BAR_FULL = "█"
BAR_HALF = "▌"

STOP_WORDS = frozenset(
    "a an the and or but in on at to for of is it this that with from by as "
    "be was were been are not no all has have had do does did will can could "
    "should would may might shall into up out if so than too very just about "
    "also each which their there then them these those its over such after "
    "before between through during without again further once here when where "
    "how what who whom why how some any many much more most other only own "
    "same few new old use used using add added adding remove removed get set".split()
)

CONVENTIONAL_TYPES = [
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert",
]

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ──────────────────────────────────────────────────────────────────────
# Git command execution
# ──────────────────────────────────────────────────────────────────────

def run_git(args: list[str], cwd: Path, timeout: int = 120) -> tuple[bool, str]:
    """Run a git command and return (success, stdout)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return False, str(exc)


def check_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    ok, _ = run_git(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return ok


def get_git_root(path: Path) -> Path:
    """Return the root of the git repository."""
    ok, out = run_git(["rev-parse", "--show-toplevel"], cwd=path)
    if ok:
        return Path(out)
    return path


# ──────────────────────────────────────────────────────────────────────
# Formatting helpers
# ──────────────────────────────────────────────────────────────────────

def fmt_number(n: int | float) -> str:
    """Format number with thousands separator."""
    if isinstance(n, float):
        return f"{n:,.1f}"
    return f"{n:,}"


def fmt_duration(days: int) -> str:
    """Format a duration in days as a human-readable string."""
    if days < 1:
        return "less than a day"
    if days == 1:
        return "1 day"
    if days < 30:
        return f"{days} days"
    months = days / 30.44
    if months < 12:
        return f"{months:.1f} months"
    years = days / 365.25
    return f"{years:.1f} years"


def fmt_pct(part: int | float, total: int | float) -> str:
    """Format a percentage."""
    if total == 0:
        return "0.0%"
    return f"{100.0 * part / total:.1f}%"


def fmt_bar_chart(
    data: dict[str, int],
    width: int = 40,
    title: str = "",
    sort_by_value: bool = False,
    max_label_len: int = 0,
) -> str:
    """Create a horizontal Unicode bar chart.

    Returns a multi-line string like:
        Label1  │████████████████ 145
        Label2  │█████████ 78
    """
    if not data:
        return "  (no data)\n"

    items = list(data.items())
    if sort_by_value:
        items.sort(key=lambda x: x[1], reverse=True)

    max_val = max(v for _, v in items) if items else 1
    if max_label_len == 0:
        max_label_len = max(len(str(k)) for k, _ in items)

    lines = []
    if title:
        lines.append(f"  {title}")
        lines.append("  " + "─" * (max_label_len + width + 12))

    for label, value in items:
        bar_len = int(width * value / max_val) if max_val > 0 else 0
        bar = BAR_FULL * bar_len
        lines.append(f"  {str(label):<{max_label_len}} │{bar} {fmt_number(value)}")

    return "\n".join(lines) + "\n"


def fmt_sparkline(values: list[int | float]) -> str:
    """Create an inline sparkline string."""
    if not values:
        return ""
    lo = min(values)
    hi = max(values)
    rng = hi - lo if hi != lo else 1
    chars = SPARKLINE_CHARS
    n = len(chars) - 1
    return "".join(chars[min(n, int((v - lo) / rng * n))] for v in values)


def fmt_table(headers: list[str], rows: list[list[str]], align: list[str] | None = None) -> str:
    """Create a Markdown table.

    align: list of 'l', 'r', or 'c' per column.
    """
    if not rows:
        return "| " + " | ".join(headers) + " |\n" + "| " + " | ".join("---" for _ in headers) + " |\n| (no data) |"

    if align is None:
        align = ["l"] * len(headers)

    # Compute column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(cell)))

    def pad(val: str, w: int, a: str) -> str:
        if a == "r":
            return str(val).rjust(w)
        if a == "c":
            return str(val).center(w)
        return str(val).ljust(w)

    def sep(w: int, a: str) -> str:
        if a == "r":
            return "-" * (w - 1) + ":"
        if a == "c":
            return ":" + "-" * (w - 2) + ":"
        return "-" * w

    header_line = "| " + " | ".join(pad(h, widths[i], align[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join(sep(max(widths[i], 3), align[i]) for i in range(len(headers))) + " |"
    body_lines = []
    for row in rows:
        cells = []
        for i in range(len(headers)):
            val = row[i] if i < len(row) else ""
            cells.append(pad(str(val), widths[i], align[i]))
        body_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join([header_line, sep_line] + body_lines)


# ──────────────────────────────────────────────────────────────────────
# Log parsing — single expensive call, reuse everywhere
# ──────────────────────────────────────────────────────────────────────

def parse_full_log(repo: Path) -> list[dict[str, Any]]:
    """Parse the full git log with numstat into a list of commit dicts.

    Each dict:
        hash, author_name, author_email, date_iso, date_relative, subject,
        datetime, files: [{path, added, deleted}]
    """
    fmt = f"{COMMIT_DELIM}%H|%aN|%aE|%ad|%ar|%s"
    ok, raw = run_git(
        ["log", "--all", "--numstat", f"--format={fmt}", "--date=iso"],
        cwd=repo,
        timeout=300,
    )
    if not ok or not raw:
        return []

    commits = []
    current: dict[str, Any] | None = None

    for line in raw.split("\n"):
        if line.startswith(COMMIT_DELIM):
            if current is not None:
                commits.append(current)
            parts = line[len(COMMIT_DELIM):].split("|", 5)
            if len(parts) < 6:
                current = None
                continue
            hash_, name, email, date_iso, date_rel, subject = parts
            try:
                dt = _parse_iso_date(date_iso)
            except Exception:
                dt = None
            current = {
                "hash": hash_,
                "author_name": name,
                "author_email": email,
                "date_iso": date_iso,
                "date_relative": date_rel,
                "subject": subject,
                "datetime": dt,
                "files": [],
            }
        elif current is not None and line and "\t" in line:
            parts = line.split("\t", 2)
            if len(parts) == 3:
                added_str, deleted_str, path = parts
                try:
                    added = int(added_str) if added_str != "-" else 0
                except ValueError:
                    added = 0
                try:
                    deleted = int(deleted_str) if deleted_str != "-" else 0
                except ValueError:
                    deleted = 0
                current["files"].append({"path": path, "added": added, "deleted": deleted})

    if current is not None:
        commits.append(current)

    return commits


def _parse_iso_date(s: str) -> datetime:
    """Parse git iso date like '2026-02-08 17:30:45 -0500'."""
    s = s.strip()
    # Try standard iso format
    for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # Fallback: drop timezone
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


# ──────────────────────────────────────────────────────────────────────
# Collectors — each takes parsed commits + repo path, returns a dict
# ──────────────────────────────────────────────────────────────────────

def collect_overview(commits: list[dict], repo: Path) -> dict[str, Any]:
    """Section 1: Repository overview."""
    total = len(commits)

    # Dates
    dates = [c["datetime"] for c in commits if c["datetime"]]
    first_date = min(dates) if dates else None
    last_date = max(dates) if dates else None
    age_days = (last_date - first_date).days + 1 if first_date and last_date else 0

    # Contributors
    authors = sorted(set(c["author_name"] for c in commits))

    # Branches
    ok, branch_raw = run_git(["branch", "-a"], cwd=repo)
    branches = [b.strip().lstrip("* ") for b in branch_raw.split("\n") if b.strip()] if ok else []
    local_branches = [b for b in branches if not b.startswith("remotes/")]
    remote_branches = [b for b in branches if b.startswith("remotes/")]

    # Current branch
    ok, current_branch = run_git(["branch", "--show-current"], cwd=repo)
    if not ok:
        current_branch = "unknown"

    # Tags
    ok, tag_raw = run_git(["tag", "-l"], cwd=repo)
    tags = [t.strip() for t in tag_raw.split("\n") if t.strip()] if ok else []

    # Repo size
    ok, size_raw = run_git(["count-objects", "-vH"], cwd=repo)
    repo_size = "unknown"
    if ok:
        for line in size_raw.split("\n"):
            if line.startswith("size-pack:"):
                repo_size = line.split(":", 1)[1].strip()
                break

    # Commits per day
    cpd = total / age_days if age_days > 0 else total

    return {
        "total_commits": total,
        "contributors": authors,
        "contributor_count": len(authors),
        "first_date": first_date,
        "last_date": last_date,
        "age_days": age_days,
        "local_branches": local_branches,
        "remote_branches": remote_branches,
        "current_branch": current_branch,
        "tags": tags,
        "repo_size": repo_size,
        "commits_per_day": cpd,
    }


def collect_contributors(commits: list[dict]) -> list[dict[str, Any]]:
    """Section 2: Per-contributor statistics."""
    author_data: dict[str, dict] = {}

    for c in commits:
        name = c["author_name"]
        if name not in author_data:
            author_data[name] = {
                "name": name,
                "email": c["author_email"],
                "commits": 0,
                "lines_added": 0,
                "lines_deleted": 0,
                "files_changed": 0,
                "first_date": c["datetime"],
                "last_date": c["datetime"],
            }
        d = author_data[name]
        d["commits"] += 1
        for f in c["files"]:
            d["lines_added"] += f["added"]
            d["lines_deleted"] += f["deleted"]
            d["files_changed"] += 1
        dt = c["datetime"]
        if dt:
            if d["first_date"] is None or dt < d["first_date"]:
                d["first_date"] = dt
            if d["last_date"] is None or dt > d["last_date"]:
                d["last_date"] = dt

    result = sorted(author_data.values(), key=lambda x: x["commits"], reverse=True)
    return result


def collect_activity(commits: list[dict]) -> dict[str, Any]:
    """Section 3: Commit activity patterns."""
    by_dow: dict[str, int] = {d: 0 for d in DAY_ORDER}
    by_hour: dict[int, int] = {h: 0 for h in range(24)}
    by_month: dict[str, int] = defaultdict(int)
    by_year: dict[int, int] = defaultdict(int)
    dates_set: set[str] = set()  # YYYY-MM-DD strings for streak calc

    for c in commits:
        dt = c["datetime"]
        if dt is None:
            continue
        dow = dt.strftime("%A")
        if dow in by_dow:
            by_dow[dow] += 1
        by_hour[dt.hour] += 1
        by_month[dt.strftime("%Y-%m")] += 1
        by_year[dt.year] += 1
        dates_set.add(dt.strftime("%Y-%m-%d"))

    # Streak calculation
    longest_streak = 0
    current_streak = 0
    if dates_set:
        sorted_dates = sorted(dates_set)
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Longest streak
        streak = 1
        for i in range(1, len(sorted_dates)):
            d1 = datetime.strptime(sorted_dates[i - 1], "%Y-%m-%d")
            d2 = datetime.strptime(sorted_dates[i], "%Y-%m-%d")
            if (d2 - d1).days == 1:
                streak += 1
            else:
                longest_streak = max(longest_streak, streak)
                streak = 1
        longest_streak = max(longest_streak, streak)

        # Current streak (counting back from today or most recent commit)
        ref = today_str if today_str in dates_set else sorted_dates[-1]
        current_streak = 1
        ref_dt = datetime.strptime(ref, "%Y-%m-%d")
        while True:
            prev = (ref_dt - timedelta(days=1)).strftime("%Y-%m-%d")
            if prev in dates_set:
                current_streak += 1
                ref_dt -= timedelta(days=1)
            else:
                break

    # Sort month keys chronologically
    sorted_months = dict(sorted(by_month.items()))

    return {
        "by_day_of_week": by_dow,
        "by_hour": by_hour,
        "by_month": sorted_months,
        "by_year": dict(sorted(by_year.items())),
        "longest_streak": longest_streak,
        "current_streak": current_streak,
        "unique_active_days": len(dates_set),
    }


def collect_code_stats(repo: Path) -> dict[str, Any]:
    """Section 4: Code statistics from current HEAD."""
    ok, file_list_raw = run_git(["ls-tree", "-r", "--name-only", "HEAD"], cwd=repo)
    if not ok or not file_list_raw:
        return {"total_files": 0, "by_extension": {}, "lines_by_extension": {},
                "largest_files": [], "total_lines": 0}

    files = [f.strip() for f in file_list_raw.split("\n") if f.strip()]
    ext_count: dict[str, int] = Counter()
    ext_lines: dict[str, int] = defaultdict(int)
    file_lines: list[tuple[str, int]] = []

    for fpath in files:
        ext = Path(fpath).suffix.lower() or "(no ext)"
        ext_count[ext] += 1

        # Count lines via git show to avoid working-tree issues
        ok2, content = run_git(["show", f"HEAD:{fpath}"], cwd=repo, timeout=10)
        if ok2:
            n = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        else:
            n = 0
        ext_lines[ext] += n
        file_lines.append((fpath, n))

    file_lines.sort(key=lambda x: x[1], reverse=True)
    total_lines = sum(v for v in ext_lines.values())

    return {
        "total_files": len(files),
        "by_extension": dict(ext_count.most_common()),
        "lines_by_extension": dict(sorted(ext_lines.items(), key=lambda x: x[1], reverse=True)),
        "largest_files": file_lines[:20],
        "total_lines": total_lines,
    }


def collect_churn(commits: list[dict], top_n: int = 20) -> dict[str, Any]:
    """Section 5: Code churn analysis."""
    file_commit_count: Counter = Counter()
    file_added: Counter = Counter()
    file_deleted: Counter = Counter()

    for c in commits:
        seen = set()
        for f in c["files"]:
            p = f["path"]
            if p not in seen:
                file_commit_count[p] += 1
                seen.add(p)
            file_added[p] += f["added"]
            file_deleted[p] += f["deleted"]

    # Churn = added + deleted
    file_churn = {p: file_added[p] + file_deleted[p] for p in file_commit_count}

    # Hotspot score = commit_count * churn
    file_hotspot = {p: file_commit_count[p] * file_churn.get(p, 0) for p in file_commit_count}

    most_modified = file_commit_count.most_common(top_n)
    highest_churn = sorted(file_churn.items(), key=lambda x: x[1], reverse=True)[:top_n]
    hotspots = sorted(file_hotspot.items(), key=lambda x: x[1], reverse=True)[:top_n]

    return {
        "most_modified": most_modified,
        "highest_churn": highest_churn,
        "hotspots": hotspots,
        "file_added": file_added,
        "file_deleted": file_deleted,
        "file_commit_count": file_commit_count,
    }


def collect_messages(commits: list[dict]) -> dict[str, Any]:
    """Section 6: Commit message analysis."""
    subjects = [c["subject"] for c in commits if c["subject"]]
    if not subjects:
        return {"total": 0, "avg_length": 0, "conventional": {}, "common_words": [],
                "length_dist": {}}

    lengths = [len(s) for s in subjects]
    avg_len = sum(lengths) / len(lengths)

    # Conventional commit detection
    conv_counts: dict[str, int] = {t: 0 for t in CONVENTIONAL_TYPES}
    other_count = 0
    for s in subjects:
        matched = False
        for t in CONVENTIONAL_TYPES:
            if re.match(rf"^{t}(\(.+\))?[!]?:", s, re.IGNORECASE):
                conv_counts[t] += 1
                matched = True
                break
        if not matched:
            other_count += 1

    conv_counts = {k: v for k, v in conv_counts.items() if v > 0}

    # Word frequency
    words: list[str] = []
    for s in subjects:
        # Remove conventional prefix
        s = re.sub(r"^\w+(\(.+\))?[!]?:\s*", "", s)
        for word in re.findall(r"[a-zA-Z]{3,}", s.lower()):
            if word not in STOP_WORDS:
                words.append(word)

    common_words = Counter(words).most_common(20)

    # Length distribution
    short = sum(1 for l in lengths if l < 30)
    medium = sum(1 for l in lengths if 30 <= l < 72)
    long_ = sum(1 for l in lengths if l >= 72)

    return {
        "total": len(subjects),
        "avg_length": avg_len,
        "min_length": min(lengths),
        "max_length": max(lengths),
        "conventional": conv_counts,
        "conventional_other": other_count,
        "common_words": common_words,
        "length_dist": {"Short (<30)": short, "Medium (30-72)": medium, "Long (>72)": long_},
    }


def collect_branches_tags(repo: Path) -> dict[str, Any]:
    """Section 7: Branch and tag details."""
    # Branches with last commit date
    ok, ref_raw = run_git(
        ["for-each-ref", "--sort=-committerdate",
         "--format=%(refname:short)|%(committerdate:short)|%(authorname)|%(subject)",
         "refs/heads/"],
        cwd=repo,
    )
    branches = []
    if ok and ref_raw:
        for line in ref_raw.split("\n"):
            parts = line.split("|", 3)
            if len(parts) >= 2:
                branches.append({
                    "name": parts[0],
                    "date": parts[1],
                    "author": parts[2] if len(parts) > 2 else "",
                    "subject": parts[3] if len(parts) > 3 else "",
                })

    # Tags with dates
    ok, tag_raw = run_git(
        ["for-each-ref", "--sort=-creatordate",
         "--format=%(refname:short)|%(creatordate:short)|%(subject)",
         "refs/tags/"],
        cwd=repo,
    )
    tags = []
    if ok and tag_raw:
        for line in tag_raw.split("\n"):
            parts = line.split("|", 2)
            if len(parts) >= 2 and parts[0]:
                tags.append({
                    "name": parts[0],
                    "date": parts[1],
                    "subject": parts[2] if len(parts) > 2 else "",
                })

    return {"branches": branches, "tags": tags}


def collect_recent(commits: list[dict], n: int = 15) -> dict[str, Any]:
    """Section 8: Recent activity."""
    recent = commits[:n]  # commits are already newest-first
    recent_files: list[str] = []
    seen: set[str] = set()
    for c in recent:
        for f in c["files"]:
            if f["path"] not in seen:
                recent_files.append(f["path"])
                seen.add(f["path"])
            if len(recent_files) >= 20:
                break
        if len(recent_files) >= 20:
            break

    return {"recent_commits": recent, "recent_files": recent_files}


def collect_growth(commits: list[dict]) -> dict[str, Any]:
    """Section 9: Growth over time."""
    if not commits:
        return {"monthly_commits": {}, "cumulative": {}}

    by_month: dict[str, int] = defaultdict(int)
    for c in commits:
        dt = c["datetime"]
        if dt:
            by_month[dt.strftime("%Y-%m")] += 1

    sorted_months = sorted(by_month.items())
    cumulative: dict[str, int] = {}
    running = 0
    for m, count in sorted_months:
        running += count
        cumulative[m] = running

    return {
        "monthly_commits": dict(sorted_months),
        "cumulative": cumulative,
    }


# ──────────────────────────────────────────────────────────────────────
# Report generator
# ──────────────────────────────────────────────────────────────────────

class GitReportGenerator:
    """Orchestrates all sections into a Markdown report."""

    def __init__(self, repo: Path, top_n: int = 20):
        self.repo = repo
        self.top_n = top_n
        self.repo_name = repo.name
        self.sections: list[str] = []
        self.generated_at = datetime.now()

    def generate(self) -> str:
        """Run all collectors and assemble the report."""
        print("  Parsing git log...", flush=True)
        commits = parse_full_log(self.repo)

        if not commits:
            return self._empty_report()

        print(f"  Found {len(commits)} commits. Collecting statistics...", flush=True)
        overview = collect_overview(commits, self.repo)
        contributors = collect_contributors(commits)
        activity = collect_activity(commits)
        print("  Analyzing code...", flush=True)
        code_stats = collect_code_stats(self.repo)
        churn = collect_churn(commits, self.top_n)
        messages = collect_messages(commits)
        bt = collect_branches_tags(self.repo)
        recent = collect_recent(commits)
        growth = collect_growth(commits)

        print("  Building report...", flush=True)
        self._add_header(overview)
        self._add_toc()
        self._add_overview(overview)
        self._add_contributors(contributors, overview)
        self._add_activity(activity, overview)
        self._add_code_stats(code_stats)
        self._add_churn(churn)
        self._add_messages(messages)
        self._add_branches_tags(bt, overview)
        self._add_recent(recent)
        self._add_growth(growth)
        self._add_footer()

        return "\n\n".join(self.sections)

    # ── Header ────────────────────────────────────────────────────────

    def _add_header(self, overview: dict) -> None:
        repo_root = get_git_root(self.repo)
        self.sections.append(
            f"# Git Repository Statistics Report\n\n"
            f"**Repository**: `{self.repo_name}`  \n"
            f"**Path**: `{repo_root}`  \n"
            f"**Generated**: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}  \n"
            f"**Commits analyzed**: {fmt_number(overview['total_commits'])}  \n"
            f"**Branch**: `{overview['current_branch']}`\n\n"
            f"---"
        )

    def _add_toc(self) -> None:
        self.sections.append(
            "## Table of Contents\n\n"
            "1. [Repository Overview](#1-repository-overview)\n"
            "2. [Contributor Statistics](#2-contributor-statistics)\n"
            "3. [Commit Activity Patterns](#3-commit-activity-patterns)\n"
            "4. [Code Statistics](#4-code-statistics)\n"
            "5. [Code Churn Analysis](#5-code-churn-analysis)\n"
            "6. [Commit Message Analysis](#6-commit-message-analysis)\n"
            "7. [Branches & Tags](#7-branches--tags)\n"
            "8. [Recent Activity](#8-recent-activity)\n"
            "9. [Repository Growth](#9-repository-growth)"
        )

    # ── Section 1: Overview ───────────────────────────────────────────

    def _add_overview(self, ov: dict) -> None:
        first = ov["first_date"].strftime("%Y-%m-%d") if ov["first_date"] else "N/A"
        last = ov["last_date"].strftime("%Y-%m-%d") if ov["last_date"] else "N/A"

        rows = [
            ["Repository Age", fmt_duration(ov["age_days"])],
            ["Total Commits", fmt_number(ov["total_commits"])],
            ["Contributors", fmt_number(ov["contributor_count"])],
            ["Local Branches", fmt_number(len(ov["local_branches"]))],
            ["Remote Branches", fmt_number(len(ov["remote_branches"]))],
            ["Tags", fmt_number(len(ov["tags"]))],
            ["Repository Size (packed)", ov["repo_size"]],
            ["First Commit", first],
            ["Latest Commit", last],
            ["Avg Commits/Day", f"{ov['commits_per_day']:.1f}"],
        ]

        table = fmt_table(["Metric", "Value"], rows, ["l", "r"])
        self.sections.append(f"## 1. Repository Overview\n\n{table}")

    # ── Section 2: Contributors ───────────────────────────────────────

    def _add_contributors(self, contribs: list[dict], overview: dict) -> None:
        lines = ["## 2. Contributor Statistics"]

        # Summary
        total_commits = overview["total_commits"]
        lines.append(f"\n**{len(contribs)}** contributor(s) — "
                      f"**{fmt_number(total_commits)}** total commits\n")

        # Table
        headers = ["#", "Contributor", "Commits", "%", "Lines ++", "Lines --", "Net", "First Active", "Last Active"]
        align = ["r", "l", "r", "r", "r", "r", "r", "c", "c"]
        rows = []
        for i, c in enumerate(contribs[:self.top_n], 1):
            net = c["lines_added"] - c["lines_deleted"]
            net_str = f"+{fmt_number(net)}" if net >= 0 else fmt_number(net)
            first = c["first_date"].strftime("%Y-%m-%d") if c["first_date"] else "?"
            last = c["last_date"].strftime("%Y-%m-%d") if c["last_date"] else "?"
            rows.append([
                str(i),
                c["name"],
                fmt_number(c["commits"]),
                fmt_pct(c["commits"], total_commits),
                f"+{fmt_number(c['lines_added'])}",
                f"-{fmt_number(c['lines_deleted'])}",
                net_str,
                first,
                last,
            ])

        lines.append(fmt_table(headers, rows, align))

        # Bar chart
        if contribs:
            chart_data = {c["name"]: c["commits"] for c in contribs[:15]}
            lines.append("\n### Commit Distribution\n")
            lines.append("```")
            lines.append(fmt_bar_chart(chart_data, width=40, title="Commits per Contributor"))
            lines.append("```")

        self.sections.append("\n".join(lines))

    # ── Section 3: Activity ───────────────────────────────────────────

    def _add_activity(self, act: dict, overview: dict) -> None:
        lines = ["## 3. Commit Activity Patterns"]

        # Day of week
        lines.append("\n### By Day of Week\n")
        dow_ordered = {d: act["by_day_of_week"].get(d, 0) for d in DAY_ORDER}
        lines.append("```")
        lines.append(fmt_bar_chart(dow_ordered, width=35, title="Commits by Day"))
        lines.append("```")

        # Hour of day
        lines.append("\n### By Hour of Day\n")
        hour_data = {f"{h:02d}:00": act["by_hour"].get(h, 0) for h in range(24)}
        lines.append("```")
        lines.append(fmt_bar_chart(hour_data, width=35, title="Commits by Hour (local time)"))
        lines.append("```")

        # Sparkline for hour
        hour_vals = [act["by_hour"].get(h, 0) for h in range(24)]
        if any(hour_vals):
            lines.append(f"\n**Hourly sparkline**: `{fmt_sparkline(hour_vals)}`\n")

        # By month
        if act["by_month"]:
            lines.append("\n### By Month\n")
            lines.append("```")
            lines.append(fmt_bar_chart(act["by_month"], width=35, title="Commits by Month"))
            lines.append("```")

            month_vals = list(act["by_month"].values())
            if len(month_vals) > 1:
                lines.append(f"\n**Monthly trend**: `{fmt_sparkline(month_vals)}`\n")

        # Streaks
        lines.append("\n### Streaks & Consistency\n")
        total = overview["total_commits"]
        rows = [
            ["Unique Active Days", fmt_number(act["unique_active_days"])],
            ["Longest Streak", f"{act['longest_streak']} day(s)"],
            ["Current Streak", f"{act['current_streak']} day(s)"],
        ]
        if overview["age_days"] > 0:
            active_pct = 100.0 * act["unique_active_days"] / overview["age_days"]
            rows.append(["Active Day Rate", f"{active_pct:.1f}%"])

        lines.append(fmt_table(["Metric", "Value"], rows, ["l", "r"]))

        self.sections.append("\n".join(lines))

    # ── Section 4: Code Stats ─────────────────────────────────────────

    def _add_code_stats(self, cs: dict) -> None:
        lines = [
            "## 4. Code Statistics",
            f"\n**{fmt_number(cs['total_files'])}** tracked files — "
            f"**{fmt_number(cs['total_lines'])}** total lines\n",
        ]

        # By extension table
        if cs["by_extension"]:
            headers = ["Extension", "Files", "Lines", "% of Lines"]
            align = ["l", "r", "r", "r"]
            rows = []
            total_l = cs["total_lines"] or 1
            for ext in list(cs["lines_by_extension"].keys())[:20]:
                rows.append([
                    ext,
                    fmt_number(cs["by_extension"].get(ext, 0)),
                    fmt_number(cs["lines_by_extension"].get(ext, 0)),
                    fmt_pct(cs["lines_by_extension"].get(ext, 0), total_l),
                ])
            lines.append("### Files by Type\n")
            lines.append(fmt_table(headers, rows, align))

        # Largest files
        if cs["largest_files"]:
            lines.append("\n### Largest Files (by line count)\n")
            headers = ["#", "File", "Lines"]
            align = ["r", "l", "r"]
            rows = []
            for i, (fpath, n) in enumerate(cs["largest_files"][:15], 1):
                rows.append([str(i), f"`{fpath}`", fmt_number(n)])
            lines.append(fmt_table(headers, rows, align))

        self.sections.append("\n".join(lines))

    # ── Section 5: Churn ──────────────────────────────────────────────

    def _add_churn(self, churn: dict) -> None:
        lines = ["## 5. Code Churn Analysis"]

        if not churn["most_modified"]:
            lines.append("\n*Not enough history for churn analysis.*")
            self.sections.append("\n".join(lines))
            return

        # Most modified
        lines.append("\n### Most Frequently Modified Files\n")
        headers = ["#", "File", "Commits", "Lines ++", "Lines --"]
        align = ["r", "l", "r", "r", "r"]
        rows = []
        for i, (path, count) in enumerate(churn["most_modified"][:self.top_n], 1):
            added = churn["file_added"].get(path, 0)
            deleted = churn["file_deleted"].get(path, 0)
            rows.append([str(i), f"`{path}`", fmt_number(count),
                         f"+{fmt_number(added)}", f"-{fmt_number(deleted)}"])
        lines.append(fmt_table(headers, rows, align))

        # Highest churn
        lines.append("\n### Highest Churn (lines added + deleted)\n")
        headers = ["#", "File", "Total Churn", "Added", "Deleted"]
        align = ["r", "l", "r", "r", "r"]
        rows = []
        for i, (path, total) in enumerate(churn["highest_churn"][:self.top_n], 1):
            added = churn["file_added"].get(path, 0)
            deleted = churn["file_deleted"].get(path, 0)
            rows.append([str(i), f"`{path}`", fmt_number(total),
                         f"+{fmt_number(added)}", f"-{fmt_number(deleted)}"])
        lines.append(fmt_table(headers, rows, align))

        # Hotspots
        has_hotspots = any(score > 0 for _, score in churn["hotspots"])
        if has_hotspots:
            lines.append("\n### Hotspots (frequency x churn)\n")
            lines.append("*High scores indicate files that change often AND have large diffs — likely candidates for refactoring.*\n")
            # Use full commit count data
            mod_lookup = churn["file_commit_count"]
            headers = ["#", "File", "Score", "Commits", "Churn"]
            align = ["r", "l", "r", "r", "r"]
            rows = []
            for i, (path, score) in enumerate(churn["hotspots"][:self.top_n], 1):
                cc = mod_lookup.get(path, 0)
                ch = churn["file_added"].get(path, 0) + churn["file_deleted"].get(path, 0)
                rows.append([str(i), f"`{path}`", fmt_number(score),
                             fmt_number(cc), fmt_number(ch)])
            lines.append(fmt_table(headers, rows, align))

        self.sections.append("\n".join(lines))

    # ── Section 6: Messages ───────────────────────────────────────────

    def _add_messages(self, msg: dict) -> None:
        lines = ["## 6. Commit Message Analysis"]

        if msg["total"] == 0:
            lines.append("\n*No commit messages to analyze.*")
            self.sections.append("\n".join(lines))
            return

        # Summary
        rows = [
            ["Total Commits", fmt_number(msg["total"])],
            ["Avg Message Length", f"{msg['avg_length']:.0f} chars"],
            ["Shortest Message", f"{msg['min_length']} chars"],
            ["Longest Message", f"{msg['max_length']} chars"],
        ]
        lines.append("")
        lines.append(fmt_table(["Metric", "Value"], rows, ["l", "r"]))

        # Length distribution
        if msg["length_dist"]:
            lines.append("\n### Message Length Distribution\n")
            lines.append("```")
            lines.append(fmt_bar_chart(msg["length_dist"], width=30, title="Message Lengths"))
            lines.append("```")

        # Conventional commits
        if msg["conventional"]:
            lines.append("\n### Conventional Commit Types\n")
            total_conv = sum(msg["conventional"].values())
            headers = ["Type", "Count", "% of Conventional"]
            align = ["l", "r", "r"]
            rows = []
            for t in CONVENTIONAL_TYPES:
                if t in msg["conventional"]:
                    rows.append([t, fmt_number(msg["conventional"][t]),
                                 fmt_pct(msg["conventional"][t], total_conv)])
            lines.append(fmt_table(headers, rows, align))
            lines.append(f"\n*{total_conv} conventional commits "
                         f"({fmt_pct(total_conv, msg['total'])} of total), "
                         f"{msg['conventional_other']} non-conventional.*")
        else:
            conv_pct = fmt_pct(0, msg["total"])
            lines.append(f"\n*No conventional commit prefixes detected ({conv_pct} usage).*")

        # Common words
        if msg["common_words"]:
            lines.append("\n### Most Common Words in Commit Messages\n")
            headers = ["Word", "Occurrences"]
            align = ["l", "r"]
            rows = [[w, fmt_number(c)] for w, c in msg["common_words"]]
            lines.append(fmt_table(headers, rows, align))

        self.sections.append("\n".join(lines))

    # ── Section 7: Branches & Tags ────────────────────────────────────

    def _add_branches_tags(self, bt: dict, overview: dict) -> None:
        lines = ["## 7. Branches & Tags"]

        # Branches
        if bt["branches"]:
            lines.append(f"\n### Branches ({len(bt['branches'])})\n")
            headers = ["Branch", "Last Commit", "Author", "Last Message"]
            align = ["l", "c", "l", "l"]
            rows = []
            for b in bt["branches"]:
                name = b["name"]
                if name == overview["current_branch"]:
                    name = f"**{name}** (current)"
                subj = b["subject"][:60] + "..." if len(b["subject"]) > 60 else b["subject"]
                rows.append([name, b["date"], b["author"], subj])
            lines.append(fmt_table(headers, rows, align))
        else:
            lines.append("\n*No local branches found.*")

        # Tags
        if bt["tags"]:
            lines.append(f"\n### Tags ({len(bt['tags'])})\n")
            headers = ["Tag", "Date", "Message"]
            align = ["l", "c", "l"]
            rows = []
            for t in bt["tags"]:
                subj = t["subject"][:60] + "..." if len(t["subject"]) > 60 else t["subject"]
                rows.append([t["name"], t["date"], subj])
            lines.append(fmt_table(headers, rows, align))
        else:
            lines.append("\n*No tags found.*")

        self.sections.append("\n".join(lines))

    # ── Section 8: Recent Activity ────────────────────────────────────

    def _add_recent(self, recent: dict) -> None:
        lines = ["## 8. Recent Activity"]

        commits = recent["recent_commits"]
        if commits:
            lines.append(f"\n### Last {len(commits)} Commits\n")
            headers = ["Hash", "Author", "When", "Message"]
            align = ["l", "l", "l", "l"]
            rows = []
            for c in commits:
                subj = c["subject"][:65] + "..." if len(c["subject"]) > 65 else c["subject"]
                rows.append([
                    f"`{c['hash'][:8]}`",
                    c["author_name"],
                    c["date_relative"],
                    subj,
                ])
            lines.append(fmt_table(headers, rows, align))

        files = recent["recent_files"]
        if files:
            lines.append(f"\n### Recently Modified Files ({len(files)})\n")
            for f in files:
                lines.append(f"- `{f}`")

        self.sections.append("\n".join(lines))

    # ── Section 9: Growth ─────────────────────────────────────────────

    def _add_growth(self, growth: dict) -> None:
        lines = ["## 9. Repository Growth"]

        monthly = growth["monthly_commits"]
        cumulative = growth["cumulative"]

        if len(monthly) < 2:
            lines.append("\n*Not enough history to show growth trends (need 2+ months).*")
            self.sections.append("\n".join(lines))
            return

        # Monthly commits chart
        lines.append("\n### Monthly Commit Volume\n")
        lines.append("```")
        lines.append(fmt_bar_chart(monthly, width=40, title="Commits per Month"))
        lines.append("```")

        # Cumulative growth
        lines.append("\n### Cumulative Commits\n")
        lines.append("```")
        lines.append(fmt_bar_chart(cumulative, width=40, title="Total Commits Over Time"))
        lines.append("```")

        # Sparklines
        if monthly:
            lines.append(f"\n**Monthly volume**: `{fmt_sparkline(list(monthly.values()))}`")
        if cumulative:
            lines.append(f"**Cumulative growth**: `{fmt_sparkline(list(cumulative.values()))}`")

        self.sections.append("\n".join(lines))

    # ── Footer ────────────────────────────────────────────────────────

    def _add_footer(self) -> None:
        elapsed = (datetime.now() - self.generated_at).total_seconds()
        self.sections.append(
            "---\n\n"
            f"*Report generated by `git_report.py` in {elapsed:.1f}s*"
        )

    # ── Empty repo fallback ───────────────────────────────────────────

    def _empty_report(self) -> str:
        return (
            f"# Git Repository Statistics Report\n\n"
            f"**Repository**: `{self.repo_name}`\n\n"
            f"No commits found. This repository appears to be empty.\n"
        )


# ──────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a comprehensive git repository statistics report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/git_report.py\n"
            "  python scripts/git_report.py --repo /path/to/repo\n"
            "  python scripts/git_report.py --output my_report.md\n"
            "  python scripts/git_report.py --top-n 30\n"
        ),
    )
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(),
        help="Path to git repository (default: current directory)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output file path (default: reports/git_stats_YYYYMMDD_HHMMSS.md)",
    )
    parser.add_argument(
        "--top-n", type=int, default=20,
        help="Number of items in top-N lists (default: 20)",
    )

    args = parser.parse_args()
    repo = args.repo.resolve()

    # Validate
    if not check_git_repo(repo):
        print(f"Error: '{repo}' is not a git repository.", file=sys.stderr)
        sys.exit(1)

    repo_root = get_git_root(repo)
    print(f"Analyzing repository: {repo_root.name}")
    print(f"  Path: {repo_root}")

    # Generate
    generator = GitReportGenerator(repo_root, top_n=args.top_n)
    report = generator.generate()

    # Determine output path
    if args.output:
        out_path = args.output.resolve()
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = repo_root / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"git_stats_{ts}.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    size_kb = out_path.stat().st_size / 1024
    print(f"\nReport saved to: {out_path}")
    print(f"  Size: {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
