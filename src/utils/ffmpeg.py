import subprocess


def run(cmd: list[str], last_n: int = 8) -> None:
    """Run an ffmpeg command, raising RuntimeError with filtered stderr on failure."""
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        noise = {"built with", "configuration", "lib", "  "}
        lines = [
            l for l in result.stderr.splitlines()
            if l and not any(n in l for n in noise)
        ]
        raise RuntimeError("\n".join(lines[-last_n:]) or result.stderr[-2000:])
