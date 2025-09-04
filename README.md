Aim for consistent streaming playback at -14 LUFS. This tool helps produce clear, balanced masters that translate across major platforms without unnecessary limiting. Dual-pass FFmpeg loudnorm sets accurate integrated loudness, and conservative true peak headroom reduces the risk of clipping or encoder artifacts. Batch processing and simple defaults aim to preserve dynamics while keeping the workflow quick.

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

## Why -14 LUFS
- Streaming consistency: Most major streaming platforms normalize playback to about -14 LUFS integrated so tracks in a playlist feel similar in loudness. A file that is louder will be turned down; a file that is quieter will be turned up.
- Headroom and quality: Leaving headroom around -1.0 to -1.5 dBTP helps avoid intersample clipping and encoder distortion. The default here uses TP -1.5 dBTP to be conservative.
- Not a regulation: Broadcast standards like EBU R128 use -23 LUFS. The -14 LUFS target is a pragmatic reference for streaming, not a rule. You can change targets with `--I`, `--TP`, and `--LRA`.
- Master for sound: Normalization will adjust playback level either way. Focus on what serves the music. If you master very loud, platforms will likely turn it down. If you master more dynamic, platforms will likely turn it up.
- Platform variation: Services can change targets or behavior over time and may offer different modes. If you must match a specific service, check its current guidance and adjust the flags accordingly.
