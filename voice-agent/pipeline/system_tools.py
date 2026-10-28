import os
import re
import subprocess
from pathlib import Path

# ── Safety blocklist for run_command ─────────────────────────────────────────

_BLOCKED = [
    r"rm\s+-[a-z]*r[a-z]*f",          # rm -rf / rm -fr
    r"rm\s+-[a-z]*f[a-z]*r",
    r"rm\s+--no-preserve-root",
    r"\bsudo\b",
    r"\bsu\b\s",
    r"\bmkfs\b",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bdd\b.*\bif=/dev/",
    r">\s*/dev/sd",
    r">\s*/dev/hd",
    r":\(\)\s*\{.*\|.*&",              # fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bhalt\b",
    r"\bpoweroff\b",
    r"curl\b.*\|\s*(ba)?sh",           # curl | bash
    r"wget\b.*\|\s*(ba)?sh",
    r"chmod\s+[0-7]*7+\s+/",          # chmod 777 / or similar on root
    r"chown\b.*\s+/[^/]",             # chown something /rootpath
    r"\biptables\b",
    r"\bufw\b",
    r">\s*/etc/",                       # overwrite system config
]

_BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in _BLOCKED]

_SKIP_DIRS = {".venv", "node_modules", "__pycache__", ".git", "snap", ".cache", ".local"}
_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z",
    ".so", ".a", ".o", ".pyc", ".onnx", ".bin", ".pt", ".pth",
    ".pdf", ".docx", ".xlsx", ".pptx",
}


def run_command(command: str, working_dir: str = "") -> str:
    """Run a shell command and return stdout + stderr. 30s timeout, 4000 char output limit."""
    for pattern in _BLOCKED_RE:
        if pattern.search(command):
            return f"Blocked: this command matches a restricted pattern. Only safe commands are allowed."

    cwd = working_dir.strip() if working_dir.strip() else str(Path.home())
    if not os.path.isdir(cwd):
        return f"Working directory not found: {cwd}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=30,
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            return f"Command completed (exit code {result.returncode}, no output)."
        if len(output) > 4000:
            output = output[:4000] + f"\n... (truncated — {len(output)} chars total)"
        return output
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Error running command: {e}"


def glob_files(path: str, pattern: str, max_results: int = 50) -> str:
    """Find files matching a glob pattern under a directory."""
    base = Path(path)
    if not base.exists():
        return f"Directory not found: {path}"
    try:
        matches = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        files = [str(m) for m in matches if m.is_file()]
        if not files:
            return f"No files found matching '{pattern}' under {path}."
        total = len(files)
        result = "\n".join(files[:max_results])
        suffix = f"\n... and {total - max_results} more." if total > max_results else ""
        return f"Found {total} file(s) matching '{pattern}':\n{result}{suffix}"
    except Exception as e:
        return f"Error: {e}"


def grep_files(path: str, pattern: str, context_lines: int = 0, file_pattern: str = "") -> str:
    """Search file contents by regex. Returns matching lines with file path and line number."""
    base = Path(path)
    if not base.exists():
        return f"Directory not found: {path}"

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex pattern: {e}"

    glob = f"**/{file_pattern}" if file_pattern else "**/*"
    results = []
    files_checked = 0

    for fpath in base.glob(glob):
        if not fpath.is_file():
            continue
        if any(part in _SKIP_DIRS for part in fpath.parts):
            continue
        if fpath.suffix.lower() in _BINARY_EXTS:
            continue
        try:
            if fpath.stat().st_size > 500_000:
                continue
        except OSError:
            continue

        files_checked += 1
        try:
            lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        for i, line in enumerate(lines):
            if not regex.search(line):
                continue
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            block = []
            for j in range(start, end):
                prefix = ">" if j == i else " "
                block.append(f"{prefix} {fpath}:{j + 1}: {lines[j]}")
            results.append("\n".join(block))
            if len(results) >= 50:
                break
        if len(results) >= 50:
            break

    if not results:
        return f"No matches for '{pattern}' in {path} ({files_checked} files checked)."
    header = f"Found {len(results)} match(es) across {files_checked} files:\n\n"
    return header + "\n\n".join(results)
