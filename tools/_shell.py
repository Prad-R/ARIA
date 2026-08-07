"""
ARIA - shared subprocess helper.
Both audio (pactl) and display (brightnessctl) control go through an
external CLI tool, check its exit code, and raise a clean RuntimeError
with the tool's own stderr on failure. This centralizes that pattern so
new system-control tools (keyboard backlight, display power, etc.) don't
have to reimplement it.
"""
import subprocess


def run_cli(binary: str, *args, timeout: int = 5) -> str:
    """
    Runs `binary` with `args`, returns stdout (stripped).
    Raises RuntimeError with the tool's stderr (or a generic message)
    on non-zero exit, so callers can surface a clear error instead of
    silently falling back to stale data.
    """
    result = subprocess.run(
        [binary] + list(args),
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or f"{binary} exited with code {result.returncode}"
        )
    return result.stdout.strip()