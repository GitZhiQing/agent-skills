#!/usr/bin/env python3
"""One-command evidence collection for video-insight (single or batch).

Runs the whole mechanical collection segment so the caller stops shuttling
between scripts: fetch -> probe -> transcribe, switching to the no-speech
screen-text branch (b1-b3, plus the OCR-side transcript assembly) when
transcribe reports no_speech; --tier L2 additionally collects the base visual
evidence (mosaic frames, frame-diff, audio). The model keeps the HITL gates
(SKILL.md §0), frame reading, content analysis and visual decisions
(grab/palette targets, crop regions).

Usage (single input):
    python pipeline.py <input> --tier L1|L2 --output-dir DIR
        [--domain finance|education|tech|none] [--screen-mode frames|ocr]

Usage (batch):
    python pipeline.py <input1> <input2> ... --tier L1|L2
    python pipeline.py --batch list.txt --tier L1|L2 [--jobs N]
        (list.txt: one input per line; blank lines and # comments skipped)

Each <input> is a video/audio file, a bilibili URL, or an existing transcript
(.srt/.txt, copied to that item's transcript.* so transcription is skipped).

Single input: prints one final JSON report and honors --output-dir as the
item's output directory directly. Batch: every item gets its own
<batch-root>/<slug>/ directory (slug clashes get -2, -3... suffixes), one
item's failure never blocks the rest, and the run ends with a batch summary
report ({batch, results[], ai_next, notes}) that is also saved to
<batch-root>/batch-report.json. Default batch root is <cwd>/video-insight/.

Idempotent: steps already recorded ok (transcribe: ok or no_speech) in each
item's manifest.json are skipped on re-run, so re-running the same batch
command only touches unfinished/failed items. Exit 0 when every item
succeeded (or was already done), 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _common import (  # noqa: E402
    default_output_dir,
    fmt_ts,
    read_json,
    update_manifest,
    write_json,
)

TRANSCRIPT_EXTS = {".srt", ".txt"}
# Readability thresholds for the OCR-side screen transcript (to be calibrated).
CONF_CLEAR = 0.90
CONF_UNREADABLE = 0.50
# Long steps: ASR polling, downloads, hosted OCR.
SLOW_STEP_TIMEOUT = 1800
STEP_TIMEOUT = 900
BATCH_REPORT_NAME = "batch-report.json"


class StepFailure(RuntimeError):
    def __init__(self, step: str, exit_code: int, payload: dict | None,
                 stderr: str):
        super().__init__(f"step '{step}' failed (exit {exit_code})")
        self.step = step
        self.exit_code = exit_code
        self.payload = payload
        self.stderr = stderr


def run_step(name: str, argv: list[str], timeout: int = STEP_TIMEOUT) -> dict | None:
    """Run one collection script; return its parsed stdout JSON (or None)."""
    try:
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / f"{name}.py"), *argv],
            capture_output=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise StepFailure(name, -1, None, f"timeout after {timeout}s")
    stdout_text = proc.stdout.decode("utf-8", "replace")
    stderr_text = proc.stderr.decode("utf-8", "replace")
    payload = None
    try:
        payload = json.loads(stdout_text)
    except (ValueError, TypeError):
        pass
    if proc.returncode != 0:
        raise StepFailure(name, proc.returncode, payload, stderr_text)
    return payload


def manifest_status(out_dir: Path, name: str) -> str | None:
    try:
        return read_json(out_dir / "manifest.json")["scripts"][name]["status"]
    except Exception:
        return None


def step_done(out_dir: Path, name: str) -> bool:
    status = manifest_status(out_dir, name)
    if status is None:
        return False
    return status == "ok" or (name == "transcribe" and status == "no_speech")


def record_declaration(out_dir: Path, key: str, value: dict) -> None:
    """Append one factual declaration to manifest.json (branch switches etc.)."""
    manifest_path = out_dir / "manifest.json"
    try:
        manifest = read_json(manifest_path) if manifest_path.exists() else {}
    except Exception:
        manifest = {}
    manifest.setdefault("declaration", {})[key] = {
        **value,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "by": "pipeline",
    }
    write_json(manifest_path, manifest)


def count_chars(text: str) -> int:
    """Same counting rule as transcribe.py: CJK/alnum chars, no punctuation."""
    return sum(1 for ch in text if ch.isalnum())


def srt_plain_text(path: Path) -> str:
    """Transcript text only: cue numbers and timestamps excluded."""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.isdigit() or " --> " in stripped:
            continue
        lines.append(stripped)
    return "\n".join(lines)


def _norm_text(text: str) -> str:
    return "".join(text.split()).casefold()


def readability_from_confidence(conf: float | None) -> str:
    if conf is None or conf < CONF_UNREADABLE:
        return "不可读"
    if conf < CONF_CLEAR:
        return "低置信"
    return "清晰"


def join_grab_ats(segments: list[dict]) -> str:
    """All suggested grab moments, de-duplicated in order, as a --at list."""
    seen: list[float] = []
    for seg in segments:
        t = float(seg["grab_at"])
        if t not in seen:
            seen.append(t)
    return ",".join(f"{t:g}" for t in seen)


def merge_event_anchors(segments_doc: dict) -> tuple[str, dict]:
    """Extend the per-screen grab list with events_in_segment anchors.

    Per-screen grab_at moments are kept first; event peak anchors then fill
    the remaining frame budget (--max-screens from the segments doc) in time
    order. Pure data plumbing — counts land in stats, nothing is judged.
    """
    segments = segments_doc.get("segments", [])
    max_screens = int((segments_doc.get("params") or {}).get("max_screens", 60))
    ats: list[float] = []
    for seg in segments:
        t = float(seg["grab_at"])
        if t not in ats:
            ats.append(t)
    candidates = sorted({
        round(float(t), 2)
        for seg in segments
        for t in (seg.get("events_in_segment") or [])
    })
    added = skipped = 0
    for t in candidates:
        if len(ats) >= max_screens:
            skipped += 1
            continue
        if t not in ats:
            ats.append(t)
            added += 1
    return ",".join(f"{t:g}" for t in sorted(ats)), {
        "anchors_added": added,
        "anchors_skipped": skipped,
    }


def assemble_screen_transcript(out_dir: Path) -> list[Path]:
    """OCR-side b4: merge screen_ocr.json into transcript.screen.srt/.json.

    Adjacent screens with identical text (typewriter splits) merge into one
    row with merged_from kept for traceability; uniform-fallback timing is
    flagged so the report can say "约" (references/无口播与批量.md §1).
    """
    segs_doc = read_json(out_dir / "data" / "screen_segments.json")
    ocr_doc = read_json(out_dir / "data" / "screen_ocr.json")
    approx = segs_doc.get("mode") == "uniform"
    ocr_by_index = {s["i"]: s for s in ocr_doc.get("screens", [])}

    rows: list[dict] = []
    for seg in segs_doc.get("segments", []):
        ocr = ocr_by_index.get(seg["i"], {})
        text = (ocr.get("full_text") or "").strip()
        conf = ocr.get("mean_confidence")
        rows.append({
            "i": seg["i"],
            "t_start": seg["t_start"],
            "t_end": seg["t_end"],
            "grab_at": seg["grab_at"],
            "basis": seg.get("basis"),
            "text": text,
            "readability": readability_from_confidence(conf) if text else "不可读",
            "mean_confidence": conf,
            "evidence_frames": [ocr["frame"]] if ocr.get("frame") else [],
        })

    merged: list[dict] = []
    for row in rows:
        if (merged and row["text"] and _norm_text(row["text"]) ==
                _norm_text(merged[-1]["text"])):
            merged[-1]["t_end"] = row["t_end"]
            merged[-1]["merged_from"].append(row["i"])
            merged[-1]["evidence_frames"].extend(row["evidence_frames"])
        else:
            merged.append({**row, "merged_from": [row["i"]]})

    srt_blocks = []
    for n, row in enumerate(merged, start=1):
        if not row["text"]:
            continue  # unreadable screens stay in the JSON, not in the SRT
        srt_blocks.append(
            f"{n}\n{fmt_ts(row['t_start'])} --> {fmt_ts(row['t_end'])}\n{row['text']}\n"
        )
    srt_path = out_dir / "transcript.screen.srt"
    srt_path.write_text("\n".join(srt_blocks), encoding="utf-8")

    json_path = out_dir / "transcript.screen.json"
    write_json(json_path, {
        "mode": segs_doc.get("mode"),
        "time_precision": "approx" if approx else "exact",
        "readability_thresholds": {
            "clear": CONF_CLEAR, "unreadable": CONF_UNREADABLE,
            "note": "OCR 置信度到三档可读度的映射阈值，待实测校准",
        },
        "merged_pairs": [r["merged_from"] for r in merged
                         if len(r["merged_from"]) > 1],
        "screens": merged,
    })
    update_manifest(out_dir, "screen_transcript", status="ok",
                    outputs=[srt_path, json_path])
    return [srt_path, json_path]


def _load_meta(out_dir: Path) -> dict:
    try:
        return read_json(out_dir / "meta.json")
    except Exception:
        return {}


def voiced_stats(out_dir: Path, transcribe_info: dict | None) -> dict:
    meta = _load_meta(out_dir)
    stats: dict = {}
    duration = meta.get("duration_s")
    chars = None
    if transcribe_info and transcribe_info.get("chars") is not None:
        chars = transcribe_info["chars"]
    else:
        txt = out_dir / "transcript.txt"
        srt = out_dir / "transcript.srt"
        if txt.exists():
            chars = count_chars(txt.read_text(encoding="utf-8"))
        elif srt.exists():
            chars = count_chars(srt_plain_text(srt))
    if duration:
        stats["duration_s"] = round(duration, 2)
    if chars is not None:
        stats["chars"] = chars
        if duration:
            stats["chars_per_sec"] = round(chars / duration, 2)
    if transcribe_info and transcribe_info.get("suspect_no_speech"):
        stats["suspect_no_speech"] = True
    return stats


def screen_stats(out_dir: Path) -> dict:
    stats: dict = {}
    try:
        segs = read_json(out_dir / "data" / "screen_segments.json")
    except Exception:
        return stats
    segments = segs.get("segments", [])
    stats["n_screens"] = len(segments)
    stats["dwell_s"] = [round(s["t_end"] - s["t_start"], 2) for s in segments]
    if segs.get("mode"):
        stats["mode"] = segs["mode"]
    # screen_segments summary counting facts, passed through untouched.
    for key in ("n_events", "n_stills", "mean_screen_s", "max_screen_s",
                "longest_still_s"):
        if key in (segs.get("summary") or {}):
            stats[key] = segs["summary"][key]
    try:
        doc = read_json(out_dir / "transcript.screen.json")
        stats["total_text_chars"] = sum(
            count_chars(r.get("text", "")) for r in doc.get("screens", [])
        )
    except Exception:
        pass
    return stats


def _transcript_ready(out_dir: Path) -> bool:
    return any((out_dir / f"transcript{name}").exists()
               for name in (".srt", ".txt", ".json"))


def collect(input_arg: str, out_dir: Path, tier: str, domain: str,
            screen_mode: str, quiet: bool = False,
            include_event_anchors: bool = False) -> tuple[dict | None, int, dict | None]:
    """Collect one input into out_dir.

    Returns (report, exit_code, error). Prints the final report (or the error
    payload) unless quiet=True, which the batch layer uses so only the batch
    summary reaches stdout.
    """
    def _emit(payload: dict) -> None:
        if not quiet:
            print(json.dumps(payload, ensure_ascii=False, indent=2))

    is_url = input_arg.startswith(("http://", "https://"))
    input_path = Path(input_arg)
    transcript_input = (
        not is_url and input_path.suffix.lower() in TRANSCRIPT_EXTS
    )
    if not is_url and not transcript_input:
        input_path = input_path.expanduser().resolve()
        if not input_path.exists():
            error = {"error": f"input not found: {input_path}"}
            _emit(error)
            return None, 1, error

    steps: dict[str, str] = {}
    extra_notes: list[str] = []
    anchor_info: dict | None = None
    video: Path | None = None

    if transcript_input:
        target = out_dir / f"transcript{input_path.suffix.lower()}"
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8", errors="replace") \
            if target.exists() else None
        source = input_path.read_text(encoding="utf-8", errors="replace")
        if existing == source:
            steps["transcript_input"] = "skipped"
        else:
            shutil.copyfile(input_path, target)
            steps["transcript_input"] = "ok"

    if is_url:
        if step_done(out_dir, "fetch"):
            steps["fetch"] = "skipped"
        else:
            run_step("fetch", [input_arg, "--output-dir", str(out_dir)],
                     timeout=SLOW_STEP_TIMEOUT)
            steps["fetch"] = "ok"
        video = out_dir / "video.mp4"
    elif not transcript_input:
        video = input_path

    if video is not None:
        if step_done(out_dir, "probe"):
            steps["probe"] = "skipped"
        else:
            run_step("probe", [str(video), "--output-dir", str(out_dir)])
            steps["probe"] = "ok"

    branch = "transcript_only" if video is None else None
    transcribe_info: dict | None = None
    if video is not None and not _transcript_ready(out_dir):
        if step_done(out_dir, "transcribe"):
            steps["transcribe"] = "skipped"
            transcribe_info = read_json(
                out_dir / "manifest.json")["scripts"]["transcribe"]
        else:
            transcribe_info = run_step(
                "transcribe",
                [str(video), "--output-dir", str(out_dir), "--domain", domain],
                timeout=SLOW_STEP_TIMEOUT,
            )
            steps["transcribe"] = "ok"
        status = transcribe_info.get("status") if transcribe_info else None
        if status == "no_speech":
            steps["transcribe"] = "no_speech"
            branch = "no_speech"
    elif video is not None:
        steps["transcribe"] = "skipped"  # transcript.* already present

    no_speech_reason = None
    if branch == "no_speech":
        record = read_json(out_dir / "manifest.json")["scripts"]["transcribe"]
        no_speech_reason = record.get("reason")
        meta = _load_meta(out_dir)
        if not meta.get("video"):
            error = {
                "error": "纯音频输入且转写为空：无画面可提取文案，如实向用户说明并停止该分支（SKILL.md §6）",
                "no_speech_reason": no_speech_reason,
            }
            _emit(error)
            return None, 1, error
        record_declaration(out_dir, "no_speech_switch", {
            "detected": no_speech_reason,
            "switched_to": "screen_text_branch (references/无口播与批量.md §1)",
        })
        if not step_done(out_dir, "extract_frames"):
            run_step("extract_frames",
                     [str(video), "--output-dir", str(out_dir), "--fps", "0.5"])
            steps["extract_frames"] = "ok"
        else:
            steps["extract_frames"] = "skipped"
        if not step_done(out_dir, "detect_changes"):
            run_step("detect_changes", [str(video), "--output-dir", str(out_dir)])
            steps["detect_changes"] = "ok"
        else:
            steps["detect_changes"] = "skipped"
        if not step_done(out_dir, "screen_segments"):
            run_step("screen_segments",
                     [str(out_dir / "data" / "changes.json"),
                      "--output-dir", str(out_dir)])
            steps["screen_segments"] = "ok"
        else:
            steps["screen_segments"] = "skipped"
        segments = read_json(
            out_dir / "data" / "screen_segments.json").get("segments", [])
        if screen_mode == "ocr":
            if not step_done(out_dir, "screen_ocr"):
                run_step("screen_ocr",
                         [str(video), "--segments",
                          str(out_dir / "data" / "screen_segments.json"),
                          "--output-dir", str(out_dir)],
                         timeout=SLOW_STEP_TIMEOUT)
                steps["screen_ocr"] = "ok"
            else:
                steps["screen_ocr"] = "skipped"
            if not step_done(out_dir, "screen_transcript"):
                assemble_screen_transcript(out_dir)
                steps["screen_transcript"] = "ok"
            else:
                steps["screen_transcript"] = "skipped"
        else:
            if not step_done(out_dir, "grab_frames"):
                segments_doc = read_json(
                    out_dir / "data" / "screen_segments.json")
                grab_argv = [str(video), "--at", join_grab_ats(segments),
                             "--label", "screen", "--output-dir", str(out_dir)]
                if include_event_anchors:
                    at_list, anchor_info = merge_event_anchors(segments_doc)
                    grab_argv[grab_argv.index("--at") + 1] = at_list
                run_step("grab_frames", grab_argv)
                steps["grab_frames"] = "ok"
            else:
                if include_event_anchors:
                    # Idempotent skip: anchors are not backfilled retroactively.
                    extra_notes.append(
                        "grab_frames 已完成，--include-event-anchors 不回溯补抓；"
                        "需锚点补抓时单步重跑 grab_frames（--at 列表含 "
                        "events_in_segment 锚点）")
                steps["grab_frames"] = "skipped"

    if branch is None:
        branch = "voiced"

    if tier == "L2":
        if video is None:
            error = {
                "error": "L2 需要视频文件（transcript-only 输入无画面可分析）",
            }
            _emit(error)
            return None, 1, error
        if branch == "voiced":
            if not step_done(out_dir, "extract_frames"):
                run_step("extract_frames",
                         [str(video), "--output-dir", str(out_dir)])
                steps["extract_frames"] = "ok"
            else:
                steps["extract_frames"] = "skipped"
        # no_speech reuses the b1 mosaic (0.5 fps) as the L2 overview.
        if not step_done(out_dir, "detect_changes"):
            run_step("detect_changes", [str(video), "--output-dir", str(out_dir)])
            steps["detect_changes"] = "ok"
        elif "detect_changes" not in steps:
            steps["detect_changes"] = "skipped"
        if not step_done(out_dir, "audio_probe"):
            if _load_meta(out_dir).get("audio"):
                run_step("audio_probe",
                         [str(video), "--output-dir", str(out_dir)])
                steps["audio_probe"] = "ok"
            else:
                steps["audio_probe"] = "skipped_no_audio_track"
        else:
            steps["audio_probe"] = "skipped"

    report = _final_report(out_dir, tier, branch, screen_mode, steps, video,
                           transcribe_info, no_speech_reason)
    if extra_notes:
        report["notes"].extend(extra_notes)
    if anchor_info:
        report["stats"].update(anchor_info)
    update_manifest(out_dir, "pipeline", status="ok",
                    extra={"tier": tier, "branch": branch,
                           "screen_mode": screen_mode})
    _emit(report)
    return report, 0, None


def _final_report(out_dir: Path, tier: str, branch: str, screen_mode: str,
                  steps: dict, video: Path | None,
                  transcribe_info: dict | None,
                  no_speech_reason: str | None) -> dict:
    ready: dict = {"manifest": str(out_dir / "manifest.json")}
    if (out_dir / "meta.json").exists():
        ready["meta"] = str(out_dir / "meta.json")
    if branch == "voiced":
        for name in ("transcript.json", "transcript.srt", "transcript.txt"):
            if (out_dir / name).exists():
                ready[name] = str(out_dir / name)
        stats = voiced_stats(out_dir, transcribe_info)
    elif branch == "no_speech":
        ready["screen_segments"] = str(out_dir / "data" / "screen_segments.json")
        ready["overview_dir"] = str(out_dir / "evidence" / "overview")
        if screen_mode == "ocr":
            ready["transcript.screen.json"] = str(out_dir / "transcript.screen.json")
            ready["transcript.screen.srt"] = str(out_dir / "transcript.screen.srt")
        else:
            ready["keyframes_dir"] = str(out_dir / "evidence" / "keyframes")
        stats = screen_stats(out_dir)
    else:
        for name in ("transcript.srt", "transcript.txt"):
            if (out_dir / name).exists():
                ready[name] = str(out_dir / name)
        stats = voiced_stats(out_dir, None)
    if tier == "L2":
        for key, path in (
            ("changes", out_dir / "data" / "changes.json"),
            ("audio", out_dir / "data" / "audio.json"),
            ("frames_overview", out_dir / "data" / "frames_overview.json"),
        ):
            if path.exists():
                ready[key] = str(path)

    ai_next: list[str] = []
    notes: list[str] = []
    if branch == "voiced":
        ai_next.append("读 transcript.*（stats 已算好，直接引用）按 SKILL.md §3 做 L1 分析：01-转写校对、02-内容分析")
        if stats.get("suspect_no_speech"):
            notes.append("suspect_no_speech=true：ASR 只吐零星文本，L1 分析前先复核是否真有口播（可能需走无口播分支）")
    elif branch == "no_speech":
        notes.append(f"b0 告知门：向用户告知无口播判定（证据：{no_speech_reason}）与模式切换、成本预估 60–150 万 token——告知即走，不等许可（references/无口播与批量.md §1）")
        notes.append("事后目检纠偏：读 evidence/overview/ 拼版，若显示说话头/采访嫌疑 → 矛盾证据，停下呈报等用户定夺（references/无口播与批量.md §1）")
        if screen_mode == "ocr":
            ai_next.append("读 transcript.screen.*（组装器已合并同文屏、标注可读度）按 §3 做 01-画面文案稿、02-内容分析")
        else:
            ai_next.append("逐屏读 evidence/keyframes/screen_*.jpg 按 references/无口播与批量.md §1 b4 成稿 transcript.screen.json（可读度三档、同文屏合并、不可读不猜写），SRT 用 screen_srt.py 渲染")
            ai_next.append("成稿后按 §3 做 01-画面文案稿、02-内容分析")
        ai_next.append(
            "分段统计（stats 的 n_events/n_screens/mean_screen_s 等）与 overview 目检矛盾时 "
            "→ screen_segments --mode uniform（或 event/调 --min-screen-gap）重分段后单步重跑对应精读步骤，"
            "uniform 段的 events_in_segment 是补抓锚点（references/无口播与批量.md §1）")
        if stats.get("mode") == "uniform":
            notes.append("uniform 兜底：屏时间为均匀采样，表述一律带「约」")
    else:
        ai_next.append("读 transcript.srt/.txt 按 SKILL.md §3 做 L1 分析（无视频：时间轴以稿内时间码为准）")
    if tier == "L2":
        ai_next.append("交互模式先过 §4.3 拼版检查点（overview + changes 摘要 + 精读节点清单），确认方向后重投入步骤（grab_frames/palette 定点）由你按需单步调用")
        if branch == "no_speech":
            notes.append("L2 通览复用 b1 拼版（0.5 fps）；音频证据见 steps.audio_probe（无音轨时为 skipped_no_audio_track）")

    return {
        "tier": tier,
        "branch": branch,
        "screen_mode": screen_mode if branch == "no_speech" else None,
        "video": str(video) if video else None,
        "steps": steps,
        "ready": ready,
        "stats": stats,
        "ai_next": ai_next,
        "notes": notes,
    }


def assign_slugs(inputs: list[str]) -> list[tuple[str, str, Path]]:
    """(input, slug, out_dir-name) per item; batch-internal clashes get -2, -3."""
    from _common import slugify

    taken: dict[str, int] = {}
    assigned = []
    for item in inputs:
        base = slugify(item)
        n = taken.get(base, 0) + 1
        taken[base] = n
        slug = base if n == 1 else f"{base}-{n}"
        assigned.append((item, slug, Path(slug)))
    return assigned


def read_batch_file(path: Path) -> list[str]:
    """One input per line; blank lines and # comments skipped."""
    inputs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            inputs.append(line)
    return inputs


def _batch_item(item: str, out_dir: Path, tier: str, domain: str,
                screen_mode: str, include_event_anchors: bool = False) -> dict:
    """Run one batch item and flatten its outcome into a summary entry."""
    entry: dict = {"input": item, "output_dir": str(out_dir)}
    try:
        report, code, error = collect(item, out_dir, tier, domain,
                                      screen_mode, quiet=True,
                                      include_event_anchors=include_event_anchors)
    except StepFailure as failure:
        entry.update({
            "status": "failed",
            "failed_step": failure.step,
            "exit_code": failure.exit_code,
            "error": (failure.payload or {}).get("error")
                     or f"step '{failure.step}' failed (exit {failure.exit_code})",
            "hint": "修复后重跑同一条批命令——幂等，只补失败条目",
        })
        return entry
    if code != 0:
        entry.update({"status": "failed", "error": (error or {}).get("error", "")})
        return entry
    entry.update({
        "status": "ok",
        "branch": report["branch"],
        "steps": report["steps"],
        "stats": report["stats"],
        "ready": report["ready"],
        "ai_next": report["ai_next"],
        "notes": report["notes"],
    })
    return entry


def run_batch(inputs: list[str], batch_root: Path, tier: str, domain: str,
              screen_mode: str, jobs: int,
              include_event_anchors: bool = False) -> tuple[dict, int]:
    """Collect every input under batch_root/<slug>/; one summary at the end."""
    batch_root.mkdir(parents=True, exist_ok=True)
    items = [(item, slug, batch_root / out_name)
             for item, slug, out_name in assign_slugs(inputs)]
    for _, slug, out_dir in items:
        out_dir.mkdir(parents=True, exist_ok=True)

    if jobs > 1:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            entries = list(pool.map(
                lambda triple: _batch_item(triple[0], triple[2], tier, domain,
                                           screen_mode, include_event_anchors),
                items,
            ))
    else:
        entries = [_batch_item(item, out_dir, tier, domain, screen_mode,
                               include_event_anchors)
                   for item, _, out_dir in items]

    for (item, slug, _), entry in zip(items, entries):
        entry["slug"] = slug

    n_ok = sum(1 for e in entries if e["status"] == "ok")
    n_failed = len(entries) - n_ok
    branches = sorted({e.get("branch") for e in entries if e.get("branch")})
    ai_next = [
        "逐条读 results[].ready/ai_next 按各自分支分析（§3 / references/无口播与批量.md §1 / §4）——每条 output_dir 独立归档",
        "对比类需求按 references/无口播与批量.md §2 产跨视频对比文档，落 <批根>/ 而非单视频目录",
    ]
    notes = [
        f"{n_ok} 条就绪" + (f"，{n_failed} 条失败（已继续跑完其余；修复后重跑同一条命令，幂等只补失败条目）" if n_failed else ""),
    ]
    if "no_speech" in branches:
        notes.append("含 no_speech 条目：逐条执行 b0 事后告知与 overview 目检纠偏（references/无口播与批量.md §1）")
    report = {
        "batch": {
            "n": len(entries), "ok": n_ok, "failed": n_failed,
            "tier": tier, "screen_mode": screen_mode, "jobs": jobs,
            "branches": branches,
        },
        "results": entries,
        "report_file": str(batch_root / BATCH_REPORT_NAME),
        "ai_next": ai_next,
        "notes": [n for n in notes if n],
    }
    write_json(batch_root / BATCH_REPORT_NAME, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report, (1 if n_failed else 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("inputs", nargs="*",
                        help="Video/audio file, bilibili URL, or transcript "
                             "(.srt/.txt); multiple items run as one batch")
    parser.add_argument("--batch", default=None,
                        help="Read inputs from a list file (one per line; "
                             "# comments); combined with positional inputs. "
                             "Using --batch always runs batch semantics")
    parser.add_argument("--tier", choices=("L1", "L2"), required=True)
    parser.add_argument("--output-dir", default=None,
                        help="Single input: that item's output directory. "
                             "Batch: the batch root (each item gets "
                             "<root>/<slug>/)")
    parser.add_argument("--domain", default="none",
                        help="Hotword preset: finance / education / tech / none")
    parser.add_argument("--screen-mode", choices=("frames", "ocr"),
                        default="frames",
                        help="no-speech branch: grab frames for the model to "
                             "read (default) or run the OCR fallback")
    parser.add_argument("--include-event-anchors", action="store_true",
                        help="frames mode: extend the grab list with "
                             "events_in_segment anchors within --max-screens "
                             "(default off; counters land in stats)")
    parser.add_argument("--jobs", type=int, default=1,
                        help="Batch concurrency (default 1 = serial; ASR "
                             "quota-friendly). Ignored for single input")
    args = parser.parse_args(argv)

    inputs = list(args.inputs)
    if args.batch:
        inputs = read_batch_file(Path(args.batch)) + inputs
    if not inputs:
        print(json.dumps({"error": "no inputs given"}, ensure_ascii=False))
        return 1
    if args.jobs < 1:
        print(json.dumps({"error": "--jobs must be >= 1"}, ensure_ascii=False))
        return 1

    if len(inputs) == 1 and not args.batch:
        out_dir = (
            Path(args.output_dir).expanduser().resolve()
            if args.output_dir
            else default_output_dir(inputs[0])
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            _, code, _ = collect(inputs[0], out_dir, args.tier, args.domain,
                                 args.screen_mode,
                                 include_event_anchors=args.include_event_anchors)
        except StepFailure as failure:
            print(json.dumps({
                "failed_step": failure.step,
                "exit_code": failure.exit_code,
                "stdout": failure.payload,
                "stderr_tail": failure.stderr[-2000:],
                "hint": "修复后重跑同一条 pipeline 命令——幂等，已完成步骤自动跳过",
            }, ensure_ascii=False, indent=2))
            return 1
        return code

    batch_root = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else Path.cwd() / "video-insight"
    )
    _, code = run_batch(inputs, batch_root, args.tier, args.domain,
                        args.screen_mode, args.jobs,
                        args.include_event_anchors)
    return code


if __name__ == "__main__":
    sys.exit(main())
