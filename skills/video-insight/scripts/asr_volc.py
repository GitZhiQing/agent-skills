#!/usr/bin/env python3
"""Thin client for the Volcengine Seed ASR "bigmodel" file API.

Pure standard library (urllib), mirroring screen_ocr.py's hosted-API pattern:
submit the audio (public URL or base64 data), poll the query endpoint until
the X-Api-Status-Code response header reports success, then normalize the
result into the srt/txt/raw pieces of the transcript.* contract.

API (录音文件识别大模型, https://docs.volcengine.com/docs/6561/2606791):
- POST {base}/api/v3/auc/bigmodel/submit  — audio + request, X-Api-Sequence: -1
- POST {base}/api/v3/auc/bigmodel/query   — poll with the same X-Api-Request-Id
- response header X-Api-Status-Code: 20000000 success, 20000001/20000002
  processing, 20000003 completed-but-no-speech (body still carries
  result.text="" — mapped to the no_speech branch, not an error); anything
  else is an error (message in X-Api-Message)
- response body: result.text + result.utterances[]{text, start_time,
  end_time} with millisecond timestamps

Config (env var > <skill>/.env, via _common.get_config):
- VOLC_BIGMODEL_API_KEY      required; console.volcengine.com/speech/new/setting/apikeys
- VOLC_BIGMODEL_RESOURCE_ID  default volc.seedasr.auc (2.0 model)
- VOLC_BIGMODEL_API_BASE     default https://openspeech.bytedance.com

Domain hotwords are fed through the Seed ASR 2.0 corpus context (上下文纠偏):
observed practice is corpus.context carrying a JSON string with a
context_data list of hint sentences.
"""

from __future__ import annotations

import base64
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import get_config  # noqa: E402

API_BASE_DEFAULT = "https://openspeech.bytedance.com"
RESOURCE_ID_DEFAULT = "volc.seedasr.auc"
KEY_NAME = "VOLC_BIGMODEL_API_KEY"
# base64 inflates payloads by ~4/3; submit beyond this refuses rather than hang
MAX_AUDIO_BYTES = 200 * 1024 * 1024

STATUS_SUCCESS = "20000000"
STATUS_PROCESSING = ("20000001", "20000002")
# 实测（2026-09-16）：无人声音频（正弦音/纯 BGM）返回 20000003，body 正常且
# result.text 为空——这是"完成但无人声"，映射 no_speech 分支而非报错。
STATUS_NO_SPEECH = "20000003"

KEY_HELP = (
    f"{KEY_NAME} 未配置：在火山引擎控制台 > 语音技术 > API Key 管理"
    "（https://console.volcengine.com/speech/new/setting/apikeys）获取，"
    "设为环境变量或写入本 skill 目录 .env（参考 .env.example）"
)


# ------------------------------------------------------------------- config

def api_config() -> dict:
    """Resolve key/base/resource id; raises with setup guidance when unset."""
    key = get_config(KEY_NAME)
    if not key:
        raise RuntimeError(KEY_HELP)
    return {
        "key": key,
        "resource_id": get_config("VOLC_BIGMODEL_RESOURCE_ID", RESOURCE_ID_DEFAULT),
        "api_base": get_config("VOLC_BIGMODEL_API_BASE", API_BASE_DEFAULT),
    }


# --------------------------------------------------------------------- HTTP

def _post_json(url: str, headers: dict[str, str], body: bytes,
               *, timeout: int = 120) -> tuple[bytes, str, str]:
    """POST and return (body, X-Api-Status-Code, X-Api-Message)."""
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    for name, value in headers.items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return (
                resp.read(),
                resp.headers.get("X-Api-Status-Code", ""),
                resp.headers.get("X-Api-Message", ""),
            )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        status = (exc.headers or {}).get("X-Api-Status-Code", "")
        message = (exc.headers or {}).get("X-Api-Message", "")
        raise RuntimeError(
            f"HTTP {exc.code} from {url}"
            f"{f' (status {status})' if status else ''}"
            f"{f': {message}' if message else ''}: {detail}"
        ) from exc


def _headers(cfg: dict, request_id: str, *, sequence: str | None = None) -> dict[str, str]:
    headers = {
        "X-Api-Key": cfg["key"],
        "X-Api-Resource-Id": cfg["resource_id"],
        "X-Api-Request-Id": request_id,
    }
    if sequence is not None:
        headers["X-Api-Sequence"] = sequence
    return headers


# ------------------------------------------------------------------ payload

def build_corpus(hotwords: str) -> dict:
    """Comma-separated hotwords -> Seed ASR corpus context (上下文纠偏)."""
    words = [w.strip() for w in hotwords.split(",") if w.strip()]
    context = {"context_data": [
        {"text": "本音频中可能出现以下专有名词：" + "、".join(words)}
    ]}
    return {"context": json.dumps(context, ensure_ascii=False)}


def build_payload(audio: str | Path, *, language: str | None, hotwords: str | None,
                  resource_id: str) -> dict:
    """Audio (public URL or local file) -> submit request body."""
    request: dict = {
        "model_name": resource_id,
        "enable_punc": True,
        "enable_itn": True,
    }
    if language:
        request["language"] = language
    if hotwords:
        request["corpus"] = build_corpus(hotwords)
    if isinstance(audio, str) and audio.startswith(("http://", "https://")):
        audio_part: dict = {"url": audio}
    else:
        path = Path(audio)
        data = path.read_bytes()
        if len(data) > MAX_AUDIO_BYTES:
            raise RuntimeError(
                f"audio too large for base64 submit ({len(data)} bytes > "
                f"{MAX_AUDIO_BYTES}): {path}"
            )
        audio_part = {
            "data": base64.b64encode(data).decode("ascii"),
            "format": path.suffix.lstrip(".").lower(),
        }
    return {"user": {"uid": "video-insight"}, "audio": audio_part, "request": request}


# ------------------------------------------------------------- submit/query

def _raise_status(stage: str, status: str, message: str, body: bytes) -> None:
    detail = body.decode("utf-8", "replace")[:500]
    raise RuntimeError(
        f"ASR {stage} failed (status {status}"
        f"{f': {message}' if message else ''})"
        f"{f': {detail}' if detail else ''}"
    )


def submit(audio: str | Path, *, language: str | None = None,
           hotwords: str | None = None, cfg: dict | None = None,
           request_id: str | None = None, timeout: int = 120) -> str:
    """Submit audio for transcription; returns the X-Api-Request-Id."""
    cfg = cfg or api_config()
    request_id = request_id or uuid.uuid4().hex
    payload = json.dumps(
        build_payload(audio, language=language, hotwords=hotwords,
                      resource_id=cfg["resource_id"]),
        ensure_ascii=False,
    ).encode("utf-8")
    body, status, message = _post_json(
        f"{cfg['api_base']}/api/v3/auc/bigmodel/submit",
        _headers(cfg, request_id, sequence="-1"),
        payload, timeout=timeout,
    )
    if status not in (STATUS_SUCCESS,) + STATUS_PROCESSING:
        _raise_status("submit", status, message, body)
    return request_id


def wait_result(request_id: str, *, cfg: dict | None = None,
                poll_interval: float = 2.0, timeout: float = 1800.0) -> dict:
    """Poll query until success; returns the full response dict."""
    cfg = cfg or api_config()
    deadline = time.monotonic() + timeout
    delay = poll_interval
    while True:
        body, status, message = _post_json(
            f"{cfg['api_base']}/api/v3/auc/bigmodel/query",
            _headers(cfg, request_id),
            b"{}", timeout=60,
        )
        if status in (STATUS_SUCCESS, STATUS_NO_SPEECH):
            return json.loads(body or b"{}")
        if status not in STATUS_PROCESSING:
            _raise_status("query", status, message, body)
        if time.monotonic() + delay > deadline:
            raise TimeoutError(
                f"ASR still processing after {timeout}s (request_id {request_id})"
            )
        time.sleep(delay)
        delay = min(delay * 1.3, 6.0)


# --------------------------------------------------------------- normalize

def ms_to_srt(ms: int) -> str:
    """Milliseconds -> SRT timestamp HH:MM:SS,mmm."""
    ms = max(0, int(ms))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def to_srt(result: dict) -> str:
    """result.utterances (ms timestamps) -> SRT text, empty utterances skipped."""
    utterances = [
        utt for utt in (result.get("result") or {}).get("utterances") or []
        if (utt.get("text") or "").strip()
    ]
    blocks = []
    for i, utt in enumerate(utterances, 1):
        blocks.append(
            f"{i}\n"
            f"{ms_to_srt(utt.get('start_time', 0))} --> {ms_to_srt(utt.get('end_time', 0))}\n"
            f"{utt['text'].strip()}"
        )
    return "\n\n".join(blocks)


def to_text(result: dict) -> str:
    return ((result.get("result") or {}).get("text") or "").strip()


# ------------------------------------------------------------------ driver

def transcribe_audio(audio: str | Path, *, language: str | None = None,
                     hotwords: str | None = None,
                     timeout: float = 1800.0) -> dict:
    """Submit + poll + normalize in one call.

    Returns {"srt", "txt", "raw", "request_id"}; an empty txt means the ASR
    completed but found no speech (BGM-only input, references/无口播与批量.md §1).
    """
    cfg = api_config()
    request_id = submit(audio, language=language, hotwords=hotwords, cfg=cfg)
    raw = wait_result(request_id, cfg=cfg, timeout=timeout)
    return {
        "srt": to_srt(raw),
        "txt": to_text(raw),
        "raw": raw,
        "request_id": request_id,
    }
