#!/usr/bin/env python3
"""OCR fallback for screen-text extraction on agents without image reading.

Reads data/screen_segments.json (from screen_segments.py), grabs one frame
per screen, runs OCR on each frame and writes data/screen_ocr.json with
per-screen text + confidence + line boxes. The agent then assembles
transcript.screen.* from that JSON without ever reading an image.

Two engines (--engine auto|api|local):
- api (default when PADDLEOCR_ACCESS_TOKEN is set): the official PaddleOCR
  hosted service at paddleocr.aistudio-app.com — pure standard library
  (urllib multipart upload, async job polling, JSONL result download).
  Free token from the aistudio.baidu.com 访问令牌 page.
- local: a local paddleocr+paddlepaddle install (heavy, ~1-2 GB), e.g.
  uv run --with paddleocr --with paddlepaddle python screen_ocr.py ...

Frames are written to evidence/ocr_frames/ and kept as evidence (each
screen's OCR text references its frame); a screen whose OCR fails records
the error instead of aborting the whole run.

Usage:
    python screen_ocr.py <input video> --segments <screen_segments.json>
        [--output-dir DIR] [--engine auto|api|local] [--model PP-OCRv5]
        [--lang ch] [--timeout 300]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    default_output_dir,
    fail_manifest,
    get_config,
    read_json,
    run,
    update_manifest,
    write_json,
)

API_BASE = "https://paddleocr.aistudio-app.com"
TOKEN_ENV = "PADDLEOCR_ACCESS_TOKEN"


# ---------------------------------------------------------------- API engine

def _multipart(fields: dict[str, str], file_name: str, data: bytes,
               mime: str) -> tuple[bytes, str]:
    boundary = "----videoinsight" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\""
            f"\r\n\r\n{value}\r\n"
        ).encode("utf-8")
    body += (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{file_name}\"\r\nContent-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    body += data + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def _http(url: str, token: str | None, *, method: str = "GET",
          body: bytes | None = None, content_type: str | None = None,
          timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, data=body, method=method)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    if content_type:
        request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def api_submit(token: str, image_bytes: bytes, *, model: str,
               base_url: str = API_BASE, timeout: int = 60) -> str:
    payload = json.dumps({
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
    })
    body, content_type = _multipart(
        {"model": model, "optionalPayload": payload},
        "frame.png", image_bytes, "image/png",
    )
    data = json.loads(_http(
        f"{base_url}/api/v2/ocr/jobs", token, method="POST",
        body=body, content_type=content_type, timeout=timeout,
    ))
    if data.get("code") != 0:
        raise RuntimeError(f"job submit failed ({data.get('code')}): {data.get('msg')}")
    job_id = (data.get("data") or {}).get("jobId")
    if not job_id:
        raise RuntimeError(f"job submit returned no jobId: {data}")
    return job_id


def api_wait(token: str, job_id: str, *, base_url: str = API_BASE,
             poll_interval: float = 2.0, timeout: float = 300.0) -> dict:
    """Poll a job until done/failed; returns the job's `data` dict."""
    deadline = time.monotonic() + timeout
    delay = poll_interval
    while True:
        data = json.loads(_http(f"{base_url}/api/v2/ocr/jobs/{job_id}", token))
        if data.get("code") != 0:
            raise RuntimeError(f"job poll failed ({data.get('code')}): {data.get('msg')}")
        job = data.get("data") or {}
        state = job.get("state")
        if state == "done":
            return job
        if state == "failed":
            raise RuntimeError(f"OCR job failed: {job.get('errorMsg')}")
        if time.monotonic() + delay > deadline:
            raise TimeoutError(f"job {job_id} still {state} after {timeout}s")
        time.sleep(delay)
        delay = min(delay * 1.3, 6.0)


def extract_screen_lines(page: dict) -> list[dict]:
    """rec_texts/rec_scores/rec_polys (or rec_boxes) -> reading-order lines."""
    pruned = (page or {}).get("prunedResult") or {}
    texts = pruned.get("rec_texts") or []
    scores = pruned.get("rec_scores") or []
    polys = pruned.get("rec_polys") or []
    boxes = pruned.get("rec_boxes") or []
    lines = []
    for k, text in enumerate(texts):
        box = None
        if k < len(polys) and polys[k]:
            box = [[round(float(p), 1) for p in pt] for pt in polys[k]]
        elif k < len(boxes) and boxes[k]:
            x1, y1, x2, y2 = (round(float(v), 1) for v in boxes[k])
            box = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        lines.append({
            "text": text,
            "confidence": round(float(scores[k]), 4) if k < len(scores) else None,
            "box": box,
        })
    lines.sort(key=lambda ln: (
        round(ln["box"][0][1], -1) if ln["box"] else 0.0,
        round(ln["box"][0][0], 1) if ln["box"] else 0.0,
    ))
    return lines


def api_result_lines(token: str, job: dict, *, timeout: int = 60) -> list[dict]:
    """Download the job's JSONL result and return reading-order lines."""
    json_url = ((job.get("resultUrl") or {}).get("jsonUrl"))
    if not json_url:
        raise RuntimeError("job result has no jsonUrl")
    # The jsonUrl is a presigned BOS link carrying its own auth in the query
    # string — an extra Authorization header makes BOS reject the request.
    raw = _http(json_url, None, timeout=timeout).decode("utf-8", "replace")
    lines: list[dict] = []
    for record in raw.splitlines():
        if not record.strip():
            continue
        payload = json.loads(record)
        for page in ((payload.get("result") or {}).get("ocrResults")) or []:
            lines.extend(extract_screen_lines(page))
    return lines


# -------------------------------------------------------------- local engine

def local_engine(lang: str):
    try:
        from paddleocr import PaddleOCR  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - depends on heavy install
        raise RuntimeError(
            "paddleocr is not installed in this interpreter; either set "
            f"{TOKEN_ENV} to use the hosted API engine, or run via "
            "uv run --with paddleocr --with paddlepaddle python screen_ocr.py ..."
        ) from exc
    try:
        return PaddleOCR(lang=lang)
    except TypeError:  # pragma: no cover - older/newer constructor kwargs
        return PaddleOCR()


def local_result_lines(engine, image: Path) -> list[dict]:
    if hasattr(engine, "ocr"):
        try:
            result = engine.ocr(str(image), cls=True)
        except TypeError:
            result = engine.ocr(str(image))
    else:  # pragma: no cover - PaddleOCR 3.x predict-only API
        result = engine.predict(str(image))
    return extract_screen_lines({"prunedResult": _as_pruned(result)})


def _as_pruned(result) -> dict:
    """Normalize PaddleOCR local outputs (2.x list / 3.x Result) into a
    prunedResult-like dict with rec_texts / rec_scores / rec_polys."""
    if not isinstance(result, (list, tuple)) or not result:
        return {}
    first = result[0]
    texts = first.get("rec_texts") if isinstance(first, dict) else getattr(first, "rec_texts", None)
    if texts is None:  # PaddleOCR 2.x: [[[box], (text, conf)], ...]
        polys, rec_texts, rec_scores = [], [], []
        for page in result:
            for item in page or []:
                box, (text, conf) = item[0], item[1]
                polys.append(box)
                rec_texts.append(text)
                rec_scores.append(conf)
        return {"rec_texts": rec_texts, "rec_scores": rec_scores, "rec_polys": polys}
    def _get(name: str):
        return first.get(name) if isinstance(first, dict) else getattr(first, name, [])
    return {
        "rec_texts": texts,
        "rec_scores": _get("rec_scores") or [],
        "rec_polys": _get("rec_polys") or [],
        "rec_boxes": _get("rec_boxes") or [],
    }


# ------------------------------------------------------------------- driver

def grab_ocr_frames(input_path: Path, segments: list[dict],
                    target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for seg in segments:
        target = target_dir / f"seg_{seg['i']:02d}_{seg['grab_at']:g}s.png"
        run([
            "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error",
            "-ss", f"{seg['grab_at']:.3f}", "-i", str(input_path),
            "-frames:v", "1", "-y", str(target),
        ])
        frames.append(target)
    return frames


def ocr_screens(segments: list[dict], frames: list[Path], *, engine_name: str,
                token: str | None, model: str, lang: str,
                timeout: float) -> list[dict]:
    screens: list[dict] = []
    if engine_name == "api":
        jobs: list[tuple[dict, Path, str]] = []
        for seg, frame in zip(segments, frames):
            jobs.append((seg, frame, api_submit(token, frame.read_bytes(), model=model)))
            time.sleep(0.3)  # courtesy pacing between submits
        for seg, frame, job_id in jobs:
            screen = _screen_record(seg, frame)
            try:
                job = api_wait(token, job_id, timeout=timeout)
                screen["lines"] = api_result_lines(token, job)
            except Exception as exc:
                screen["error"] = str(exc)[:500]
            screens.append(screen)
    else:
        engine = local_engine(lang)
        for seg, frame in zip(segments, frames):
            screen = _screen_record(seg, frame)
            try:
                screen["lines"] = local_result_lines(engine, frame)
            except Exception as exc:  # pragma: no cover - engine-dependent
                screen["error"] = str(exc)[:500]
            screens.append(screen)
    for screen in screens:
        lines = screen.get("lines") or []
        confidences = [ln["confidence"] for ln in lines if ln["confidence"] is not None]
        screen["full_text"] = "\n".join(ln["text"] for ln in lines)
        screen["mean_confidence"] = (
            round(sum(confidences) / len(confidences), 4) if confidences else None
        )
    return screens


def _screen_record(seg: dict, frame: Path) -> dict:
    return {
        "i": seg["i"],
        "t_start": seg["t_start"],
        "t_end": seg["t_end"],
        "grab_at": seg["grab_at"],
        "basis": seg.get("basis"),
        "frame": str(frame),
        "lines": [],
    }


def pick_engine(requested: str, token: str | None) -> tuple[str, str | None]:
    """Resolve auto -> api when a token exists, else local."""
    if requested == "api":
        if not token:
            raise RuntimeError(
                f"--engine api needs ${TOKEN_ENV} "
                "(free token: aistudio.baidu.com 访问令牌页)"
            )
        return "api", token
    if requested == "local":
        return "local", None
    return ("api", token) if token else ("local", None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", help="Video file")
    parser.add_argument("--segments", required=True,
                        help="data/screen_segments.json from screen_segments.py")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--engine", choices=("auto", "api", "local"), default="auto")
    parser.add_argument("--model", default="PP-OCRv5",
                        help="API engine model (default PP-OCRv5)")
    parser.add_argument("--lang", default="ch", help="Local engine language (default ch)")
    parser.add_argument("--timeout", type=float, default=300.0,
                        help="Per-job poll timeout in seconds (default 300)")
    args = parser.parse_args(argv)

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        print(json.dumps({"error": f"input not found: {input_path}"}))
        return 1
    segments_path = Path(args.segments).expanduser().resolve()
    if not segments_path.exists():
        print(json.dumps({"error": f"segments not found: {segments_path}"}))
        return 1
    out_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else default_output_dir(input_path)
    )

    try:
        engine, token = pick_engine(args.engine, get_config(TOKEN_ENV))
        segments = read_json(segments_path).get("segments") or []
        if not segments:
            raise RuntimeError(f"no segments in {segments_path}")
        frames = grab_ocr_frames(input_path, segments, out_dir / "evidence" / "ocr_frames")
        screens = ocr_screens(
            segments, frames, engine_name=engine, token=token,
            model=args.model, lang=args.lang, timeout=args.timeout,
        )
        failed = [s for s in screens if s.get("error")]
        if not screens or len(failed) == len(screens):
            raise RuntimeError(
                "every screen failed OCR: "
                + "; ".join(s["error"] for s in failed[:3])
            )
        payload = {
            "input": str(input_path),
            "segments_file": str(segments_path),
            "engine": engine,
            "model": args.model if engine == "api" else f"local:{args.lang}",
            "screens": screens,
            "summary": {
                "n_screens": len(screens),
                "screens_with_text": sum(1 for s in screens if s["full_text"]),
                "screens_failed": len(failed),
            },
        }
        ocr_path = out_dir / "data" / "screen_ocr.json"
        write_json(ocr_path, payload)
        outputs = [ocr_path] + frames
        record = update_manifest(out_dir, "screen_ocr", status="ok", outputs=outputs)
        print(json.dumps({**payload["summary"], "engine": engine,
                          "status": record["status"]}, ensure_ascii=False))
        return 0
    except Exception as exc:
        fail_manifest(out_dir, "screen_ocr", exc)
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
