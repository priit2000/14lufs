# Repository Guidelines

## Project Structure and Modules
- Root: `14lufs.py` (CLI to normalize audio to -14 LUFS using FFmpeg loudnorm, dual-pass).
- Inputs: audio files can be placed at the repo root (for example, `audiitorid.mp3`).
- Outputs: created next to inputs by default using suffix `_-14LUFS` (for example, `song_-14LUFS.mp3`).

## Build, Run, and Development
- Run one file: `python 14lufs.py input.mp3`
- Set output path: `python 14lufs.py input.mp3 -o out.mp3`
- Batch normalize: `python 14lufs.py in1.mp3 in2.wav --bitrate 192k`
- Verify FFmpeg: `ffmpeg -version` (FFmpeg must be on your PATH)
- Python: version 3.8 or newer.

## Coding Style and Naming
- Style: PEP 8, 4-space indentation, snake_case for functions and variables.
- ASCII only: use plain ASCII characters. Never use typographic dashes, smart quotes, or ellipsis.
- Types: use type hints for public functions and return values.
- Docstrings: short summary plus arguments and returns for non-trivial functions.
- Formatting and linting: Black (line length 88) and Ruff/Flake8 are recommended before PRs.
- Filenames/CLI: keep the main entry as `14lufs.py`; create helper modules only if the code grows.

## Testing Guidelines
- Framework: Pytest (suggested). Place tests under `tests/` and name them `test_*.py`.
- Suggested tests: argument parsing, `default_out_path` behavior, and mocking `subprocess.run` to avoid calling FFmpeg.
- Run tests: `pytest -q`

## Commit and Pull Requests
- Commits: concise, action-oriented messages; Conventional Commits are encouraged (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`).
- PRs should include: summary, motivation, usage examples, and any platform-specific notes (Windows vs POSIX).

## Security and Configuration
- Dependencies: requires FFmpeg in PATH; avoid running from untrusted paths.
- Large files: do not commit large audio; use small samples or exclude via `.gitignore`.
- Safety: the tool writes new files by default; it avoids overwriting unless explicitly requested.
