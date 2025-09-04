# 14 LUFS Audio Normalizer

A small Python tool that normalizes audio to -14 LUFS using FFmpeg loudnorm (dual-pass). Ships with a simple GUI by default and a CLI mode for batch work.

## Features
- Dual-pass loudnorm to target -14 LUFS, TP -1.5 dBTP, LRA 11.
- GUI: file picker, parameters, per-file progress, last-folder memory.
- No overwrite: auto suffixes output with `-001`, `-002` when needed.
- Bitrate: auto-probes from source (ffprobe) if not specified.
- Channels: keep/mono/stereo toggle.

## Requirements
- Python 3.8+
- FFmpeg in your PATH (ffprobe recommended for best progress/bitrate detection)

## Quick Start (Windows)
- GUI (default):
  - `python.exe .\14lufs.py`
- CLI examples:
  - Single: `python.exe .\14lufs.py --no-gui input.mp3 -o out.mp3`
  - Batch: `python.exe .\14lufs.py --no-gui in1.mp3 in2.wav`
  - Keep source bitrate, force mono: `--channels mono`
  - Explicit bitrate: `--bitrate 192k`

## How It Works
1) First pass measures loudness with `loudnorm` (print_format=json).
2) Second pass applies normalization using measured values.
3) Output filename defaults to `<name>_-14LUFS<ext>`; if it exists, `-001`, `-002` are appended.

## Options (CLI)
- `--I`, `--TP`, `--LRA`: target LUFS / true peak / loudness range.
- `--bitrate 192k`: set output audio bitrate (if omitted, probe from input when possible).
- `--channels {mono|stereo}`: force channel count (otherwise kept).
- `-o out.ext`: single output path when processing exactly one input.
- `--no-gui`: disable GUI and run CLI.

## Notes
- Progress bar percentage is based on media duration (ffprobe preferred). If duration cannot be determined, the GUI shows a spinner per file but the job still completes.
- Large audio/media should not be committed; see `.gitignore`.
