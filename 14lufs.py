#!/usr/bin/env python3
# 14lufs.py
#
# Convert audio to -14 LUFS using FFmpeg's loudnorm (dual pass).
# Requires: Python 3.8+, ffmpeg in PATH.
#
# Usage:
#   GUI (default on Windows):
#     python.exe .\14lufs.py
#   CLI examples:
#     python.exe .\14lufs.py --no-gui input.mp3
#     python.exe .\14lufs.py --no-gui input.mp3 -o out.mp3
#     python.exe .\14lufs.py --no-gui in1.mp3 in2.wav --bitrate 192k --channels stereo
#
import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional, Dict, List, Callable

# Lazy import tkinter only if GUI is needed (some environments lack Tk)
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:  # pragma: no cover
    tk = None
    filedialog = None
    messagebox = None

LOUDNORM_DEFAULTS = {
    "I": -14.0,    # target integrated loudness in LUFS
    "TP": -1.5,    # true peak limit in dBTP
    "LRA": 11.0,   # target loudness range
}

JSON_BLOCK_RE = re.compile(r"\{\s*\"input_i\"[\s\S]*?\}", re.MULTILINE)
DURATION_RE = re.compile(r"Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found in PATH. Install ffmpeg first.", file=sys.stderr)
        sys.exit(1)


def hhmmss_to_seconds(h: int, m: int, s: int, cs: int) -> float:
    # cs are centiseconds in typical ffmpeg Duration line
    return h * 3600.0 + m * 60.0 + s + cs / 100.0


def probe_duration_seconds(infile: Path) -> Optional[float]:
    """Return media duration in seconds using ffprobe, fallback to parsing ffmpeg banner.
    Returns None if duration cannot be determined.
    """
    # Try ffprobe first
    if shutil.which("ffprobe"):
        try:
            proc = subprocess.run([
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(infile)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                val = proc.stdout.strip()
                if val:
                    return float(val)
        except Exception:
            pass
    # Fallback: parse Duration line from ffmpeg -i stderr
    try:
        proc = subprocess.run([
            "ffmpeg", "-hide_banner", "-i", str(infile),
            "-f", "null", "-"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        m = DURATION_RE.search(proc.stderr)
        if m:
            h, mi, s, cs = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
            return hhmmss_to_seconds(h, mi, s, cs)
    except Exception:
        pass
    return None


def probe_bitrate_k(infile: Path) -> Optional[str]:
    """Return audio stream bitrate as a string like '192k' using ffprobe if available."""
    if shutil.which("ffprobe"):
        try:
            proc = subprocess.run([
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=bit_rate",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(infile)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if proc.returncode == 0:
                val = proc.stdout.strip()
                if val.isdigit():
                    bps = int(val)
                    if bps > 0:
                        return f"{max(1, int(round(bps/1000)))}k"
        except Exception:
            pass
    return None

def first_pass_measurements(infile: Path, I: float, TP: float, LRA: float) -> dict:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i", str(infile),
        "-af", f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json",
        "-f", "null", "-"
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stderr = proc.stderr

    match = JSON_BLOCK_RE.search(stderr)
    if not match:
        print("Failed to parse loudnorm JSON from FFmpeg first pass.", file=sys.stderr)
        # Print a helpful tail of stderr for debugging
        print(stderr[-1000:], file=sys.stderr)
        sys.exit(2)

    data = json.loads(match.group(0))
    # Map ffmpeg's keys to second-pass params
    mapped = {
        "measured_I": float(data["input_i"]),
        "measured_LRA": float(data["input_lra"]),
        "measured_TP": float(data["input_tp"]),
        "measured_thresh": float(data["input_thresh"]),
        "offset": float(data["target_offset"]),
    }
    return mapped

def second_pass_normalize(infile: Path, outfile: Path, I: float, TP: float, LRA: float,
                          measures: Dict[str, float], bitrate: Optional[str],
                          on_progress: Optional[Callable[[float], None]] = None,
                          duration_seconds: Optional[float] = None,
                          channels: Optional[int] = None):
    loudnorm_filter = (
        f"loudnorm="
        f"I={I}:TP={TP}:LRA={LRA}:"
        f"measured_I={measures['measured_I']}:"
        f"measured_TP={measures['measured_TP']}:"
        f"measured_LRA={measures['measured_LRA']}:"
        f"measured_thresh={measures['measured_thresh']}:"
        f"offset={measures['offset']}:"
        f"linear=true:print_format=summary"
    )

    cmd = [
        "ffmpeg",
        # Do not force overwrite; script ensures unique output path.
        "-hide_banner",
        "-nostats",
        "-i", str(infile),
        "-af", loudnorm_filter,
        "-progress", "pipe:1",
    ]

    # Encode to MP3 if output endswith .mp3, else let ffmpeg infer by extension
    if outfile.suffix.lower() == ".mp3":
        cmd += ["-c:a", "libmp3lame"]
        if not bitrate:
            bitrate = probe_bitrate_k(infile)
        if bitrate:
            cmd += ["-b:a", bitrate]
    else:
        # Keep codec default based on extension
        if not bitrate and outfile.suffix.lower() in {".mp3", ".m4a", ".aac", ".opus", ".ogg"}:
            bitrate = probe_bitrate_k(infile)
        if bitrate and outfile.suffix.lower() in {".mp3", ".m4a", ".aac", ".opus", ".ogg"}:
            cmd += ["-b:a", bitrate]

    if channels in (1, 2):
        cmd += ["-ac", str(channels)]

    cmd += [str(outfile)]

    # Execute and parse progress
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, universal_newlines=True)

    # Determine duration if not provided
    if duration_seconds is None:
        duration_seconds = probe_duration_seconds(infile)

    out = []
    err_tail = []
    try:
        while True:
            line = proc.stdout.readline() if proc.stdout else ''
            if not line:
                if proc.poll() is not None:
                    break
            else:
                out.append(line)
                if on_progress and duration_seconds and duration_seconds > 0:
                    # Parse structured progress lines
                    line = line.strip()
                    if line.startswith("out_time_ms="):
                        try:
                            ms = float(line.split("=", 1)[1])
                            frac = max(0.0, min(1.0, (ms / 1000.0) / duration_seconds))
                            on_progress(frac)
                        except Exception:
                            pass
                    elif line.startswith("out_time_us="):
                        try:
                            us = float(line.split("=", 1)[1])
                            frac = max(0.0, min(1.0, (us / 1_000_000.0) / duration_seconds))
                            on_progress(frac)
                        except Exception:
                            pass
                    elif line.startswith("out_time="):
                        try:
                            t = line.split("=", 1)[1]
                            # Format HH:MM:SS.microseconds
                            hh, mm, ss_us = t.split(":")
                            ss = float(ss_us)
                            total = int(hh) * 3600 + int(mm) * 60 + ss
                            frac = max(0.0, min(1.0, total / duration_seconds))
                            on_progress(frac)
                        except Exception:
                            pass
            # drain some stderr to keep buffers flowing
            if proc.stderr and not proc.stderr.closed and proc.stderr.readable():
                try:
                    chunk = proc.stderr.readline()
                    if chunk:
                        err_tail.append(chunk)
                        if len(err_tail) > 200:
                            err_tail = err_tail[-200:]
                except Exception:
                    pass
        proc.wait()
    finally:
        if on_progress:
            # Ensure 100% on completion
            on_progress(1.0)

    if proc.returncode != 0:
        print("FFmpeg second pass failed.", file=sys.stderr)
        tail = "".join(err_tail)[-2000:]
        print(tail, file=sys.stderr)
        sys.exit(3)

def default_out_path(infile: Path, explicit_out: Optional[str]) -> Path:
    if explicit_out:
        return Path(explicit_out)
    stem = infile.stem + "_-14LUFS"
    ext = infile.suffix or ".mp3"
    return infile.with_name(stem + ext)


def avoid_overwrite_path(path: Path) -> Path:
    """Return a unique path without overwriting existing files.

    If `path` exists, append a three-digit numeric suffix before the extension:
    "-001", "-002", ... up to "-999", and return the first available.
    """
    if not path.exists():
        return path
    for i in range(1, 1000):
        suffix = f"-{i:03d}"
        candidate = path.with_name(f"{path.stem}{suffix}{path.suffix}")
        if not candidate.exists():
            return candidate
    print(
        f"Refusing to overwrite: exhausted suffixes -001..-999 for '{path.name}'.",
        file=sys.stderr,
    )
    sys.exit(6)

def normalize_one(infile: Path, outpath: Path, I: float, TP: float, LRA: float, bitrate: Optional[str],
                  on_progress: Optional[Callable[[float], None]] = None,
                  channels: Optional[int] = None):
    if not infile.exists():
        print(f"Input file not found: {infile}", file=sys.stderr)
        sys.exit(4)
    outpath = avoid_overwrite_path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)

    measures = first_pass_measurements(infile, I, TP, LRA)
    duration = probe_duration_seconds(infile)
    second_pass_normalize(
        infile,
        outpath,
        I,
        TP,
        LRA,
        measures,
        bitrate,
        on_progress=on_progress,
        duration_seconds=duration,
        channels=channels,
    )
    print(f"OK: {infile.name} -> {outpath}")

def parse_args():
    p = argparse.ArgumentParser(
        description="Normalize audio to -14 LUFS with FFmpeg loudnorm (dual pass)."
    )
    p.add_argument("inputs", nargs="*", help="Input audio file(s)")
    p.add_argument("-o", "--output", help="Single output file path (only if one input)")
    p.add_argument("--bitrate", help="Audio bitrate for output, e.g. 192k (optional)")
    p.add_argument("--I", type=float, default=LOUDNORM_DEFAULTS["I"], help="Target LUFS (default: -14)")
    p.add_argument("--TP", type=float, default=LOUDNORM_DEFAULTS["TP"], help="True peak dBTP (default: -1.5)")
    p.add_argument("--LRA", type=float, default=LOUDNORM_DEFAULTS["LRA"], help="Loudness range (default: 11)")
    p.add_argument("--no-gui", action="store_true", help="Run in CLI mode (do not launch GUI)")
    p.add_argument("--channels", choices=["mono", "stereo"], help="Force output channels to mono (1) or stereo (2)")
    return p.parse_args()


def launch_gui():
    if tk is None:
        print("Tkinter not available. Use --no-gui for CLI mode.", file=sys.stderr)
        sys.exit(7)

    root = tk.Tk()
    root.title("14 LUFS Normalizer (FFmpeg loudnorm)")

    # State
    selected_files: List[Path] = []
    last_dir: Path = Path.cwd()

    # Helpers
    def append_log(msg: str) -> None:
        def _do():
            log.configure(state="normal")
            log.insert(tk.END, msg + "\n")
            log.see(tk.END)
            log.configure(state="disabled")
        root.after(0, _do)

    # Progress helpers (thread-safe)
    file_progress_determinate = {"value": False}

    def file_progress_start_indeterminate():
        def _do():
            file_label.configure(text="Processing...")
            file_bar.configure(mode='indeterminate')
            file_bar.start(10)
        root.after(0, _do)

    def file_progress_set_fraction(frac: float):
        def _do():
            if not file_progress_determinate["value"]:
                file_bar.stop()
                file_bar.configure(mode='determinate', maximum=100)
                file_progress_determinate["value"] = True
            pct = max(0, min(100, int(frac * 100)))
            file_bar['value'] = pct
            file_label.configure(text=f"{pct}%")
        root.after(0, _do)

    def file_progress_reset():
        def _do():
            file_bar.stop()
            file_bar.configure(mode='determinate', maximum=100)
            file_bar['value'] = 0
            file_label.configure(text="0%")
            file_progress_determinate["value"] = False
        root.after(0, _do)

    def refresh_files_view():
        files_list.delete(0, tk.END)
        for p in selected_files:
            files_list.insert(tk.END, str(p))
        if len(selected_files) == 1:
            out_entry.configure(state="normal")
            out_btn.configure(state="normal")
        else:
            out_entry.delete(0, tk.END)
            out_entry.insert(0, "(outputs next to inputs)")
            out_entry.configure(state="disabled")
            out_btn.configure(state="disabled")

    def add_files():
        nonlocal last_dir
        paths = filedialog.askopenfilenames(title="Select audio files", initialdir=str(last_dir))
        if not paths:
            return
        for p in paths:
            pp = Path(p)
            if pp not in selected_files:
                selected_files.append(pp)
        # Remember the directory of the first selected file
        try:
            last_dir = Path(paths[0]).parent
            # If single selection, probe bitrate and prefill
            if len(paths) == 1:
                br = probe_bitrate_k(Path(paths[0]))
                if br:
                    b_entry.delete(0, tk.END)
                    b_entry.insert(0, br)
        except Exception:
            pass
        refresh_files_view()

    def clear_files():
        selected_files.clear()
        refresh_files_view()

    def browse_output():
        nonlocal last_dir
        if len(selected_files) != 1:
            return
        init_name = f"{selected_files[0].stem}_-14LUFS{selected_files[0].suffix or '.mp3'}"
        outp = filedialog.asksaveasfilename(title="Select output file",
                                            initialfile=init_name,
                                            initialdir=str(last_dir),
                                            defaultextension=selected_files[0].suffix or ".mp3")
        if outp:
            out_entry.configure(state="normal")
            out_entry.delete(0, tk.END)
            out_entry.insert(0, outp)
            # Remember chosen directory
            try:
                last_dir = Path(outp).parent
            except Exception:
                pass

    def run_work():
        # Validate
        if not selected_files:
            messagebox.showwarning("No files", "Please add one or more input audio files.")
            return
        try:
            I_val = float(i_entry.get())
            TP_val = float(tp_entry.get())
            LRA_val = float(lra_entry.get())
        except ValueError:
            messagebox.showerror("Invalid parameters", "I/TP/LRA must be numbers.")
            return

        bitrate_val = b_entry.get().strip() or None
        explicit_out = None
        if len(selected_files) == 1:
            val = out_entry.get().strip()
            if val and not val.startswith("(outputs "):
                explicit_out = val
        # Channels selection
        ch_val: Optional[int] = None
        if channels_var.get() == "mono":
            ch_val = 1
        elif channels_var.get() == "stereo":
            ch_val = 2

        # Check ffmpeg availability here (GUI-friendly)
        if not shutil.which("ffmpeg"):
            messagebox.showerror("FFmpeg missing", "ffmpeg not found in PATH. Install ffmpeg first.")
            return

        # Disable controls during run
        run_btn.configure(state="disabled")
        add_btn.configure(state="disabled")
        clear_btn.configure(state="disabled")

        def worker():
            try:
                for inp in selected_files:
                    try:
                        outp = default_out_path(inp, explicit_out)
                        append_log(f"Processing: {inp}")
                        file_progress_reset()
                        file_progress_start_indeterminate()
                        normalize_one(
                            inp,
                            outp,
                            I_val,
                            TP_val,
                            LRA_val,
                            bitrate_val,
                            on_progress=file_progress_set_fraction,
                            channels=ch_val,
                        )
                        append_log(f"Done: {outp}")
                    except SystemExit as e:
                        append_log(f"Error processing {inp}: exit code {e.code}")
                    except Exception as e:
                        append_log(f"Error processing {inp}: {e}")
                    finally:
                        pass
            finally:
                run_btn.configure(state="normal")
                add_btn.configure(state="normal")
                clear_btn.configure(state="normal")

        threading.Thread(target=worker, daemon=True).start()

    # Layout
    frm_files = tk.LabelFrame(root, text="Input Files")
    frm_files.pack(fill="both", padx=8, pady=6)

    files_list = tk.Listbox(frm_files, width=80, height=6)
    files_list.pack(side=tk.LEFT, fill="both", expand=True, padx=(8, 4), pady=8)
    btns = tk.Frame(frm_files)
    btns.pack(side=tk.RIGHT, padx=(4, 8), pady=8)
    add_btn = tk.Button(btns, text="Add Files...", command=add_files)
    add_btn.pack(fill="x")
    clear_btn = tk.Button(btns, text="Clear", command=clear_files)
    clear_btn.pack(fill="x", pady=(6, 0))

    frm_out = tk.LabelFrame(root, text="Output (single input only)")
    frm_out.pack(fill="x", padx=8, pady=6)
    out_entry = tk.Entry(frm_out, width=70)
    out_entry.pack(side=tk.LEFT, padx=(8, 4), pady=8)
    out_btn = tk.Button(frm_out, text="Browse...", command=browse_output)
    out_btn.pack(side=tk.RIGHT, padx=(4, 8), pady=8)

    frm_params = tk.LabelFrame(root, text="Parameters")
    frm_params.pack(fill="x", padx=8, pady=6)

    tk.Label(frm_params, text="I (LUFS)").grid(row=0, column=0, padx=8, pady=6, sticky="w")
    i_entry = tk.Entry(frm_params, width=10)
    i_entry.grid(row=0, column=1, padx=4, pady=6, sticky="w")
    i_entry.insert(0, str(LOUDNORM_DEFAULTS["I"]))

    tk.Label(frm_params, text="TP (dBTP)").grid(row=0, column=2, padx=8, pady=6, sticky="w")
    tp_entry = tk.Entry(frm_params, width=10)
    tp_entry.grid(row=0, column=3, padx=4, pady=6, sticky="w")
    tp_entry.insert(0, str(LOUDNORM_DEFAULTS["TP"]))

    tk.Label(frm_params, text="LRA").grid(row=0, column=4, padx=8, pady=6, sticky="w")
    lra_entry = tk.Entry(frm_params, width=10)
    lra_entry.grid(row=0, column=5, padx=4, pady=6, sticky="w")
    lra_entry.insert(0, str(LOUDNORM_DEFAULTS["LRA"]))

    tk.Label(frm_params, text="Bitrate (e.g. 192k)").grid(row=1, column=0, padx=8, pady=6, sticky="w")
    b_entry = tk.Entry(frm_params, width=12)
    b_entry.grid(row=1, column=1, padx=4, pady=6, sticky="w")
    # Channels toggle
    tk.Label(frm_params, text="Channels").grid(row=1, column=2, padx=8, pady=6, sticky="w")
    channels_var = tk.StringVar(value="keep")
    rb_keep = tk.Radiobutton(frm_params, text="Keep", variable=channels_var, value="keep")
    rb_keep.grid(row=1, column=3, padx=4, pady=6, sticky="w")
    rb_mono = tk.Radiobutton(frm_params, text="Mono", variable=channels_var, value="mono")
    rb_mono.grid(row=1, column=4, padx=4, pady=6, sticky="w")
    rb_stereo = tk.Radiobutton(frm_params, text="Stereo", variable=channels_var, value="stereo")
    rb_stereo.grid(row=1, column=5, padx=4, pady=6, sticky="w")

    frm_actions = tk.Frame(root)
    frm_actions.pack(fill="x", padx=8, pady=6)
    run_btn = tk.Button(frm_actions, text="Run", command=run_work)
    run_btn.pack(side=tk.LEFT, padx=(8, 4))
    quit_btn = tk.Button(frm_actions, text="Quit", command=root.destroy)
    quit_btn.pack(side=tk.LEFT, padx=4)

    # Progress section
    frm_prog = tk.LabelFrame(root, text="Progress")
    frm_prog.pack(fill="x", padx=8, pady=6)
    # Per-file progress (switches from indeterminate to determinate)
    file_bar = ttk.Progressbar(frm_prog, orient=tk.HORIZONTAL, mode='determinate', length=400, maximum=100)
    file_bar.pack(fill="x", padx=8, pady=(8, 2))
    file_label = tk.Label(frm_prog, text="0%")
    file_label.pack(anchor="w", padx=8, pady=(0, 8))

    frm_log = tk.LabelFrame(root, text="Log")
    frm_log.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    log = tk.Text(frm_log, width=80, height=12, state="disabled")
    log.pack(fill="both", expand=True, padx=8, pady=8)

    refresh_files_view()
    root.mainloop()

def main():
    # Accept GUI default when no inputs and no --no-gui
    # For CLI usage, require --no-gui or positional inputs
    try:
        args = parse_args()
    except SystemExit:
        # argparse will print help if needed
        return

    if not args.no_gui and len(sys.argv) == 1:
        launch_gui()
        return

    # CLI mode
    check_ffmpeg()
    inputs = [Path(x) for x in args.inputs]
    if not inputs:
        print("No inputs provided. Run without arguments to use the GUI.", file=sys.stderr)
        sys.exit(8)

    if args.output and len(inputs) != 1:
        print("Use --output only with a single input file.", file=sys.stderr)
        sys.exit(5)

    # Channels from CLI
    ch_cli: Optional[int] = None
    if args.channels == "mono":
        ch_cli = 1
    elif args.channels == "stereo":
        ch_cli = 2

    for inp in inputs:
        outp = default_out_path(inp, args.output)
        normalize_one(inp, outp, args.I, args.TP, args.LRA, args.bitrate, channels=ch_cli)

if __name__ == "__main__":
    main()
