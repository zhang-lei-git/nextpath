"""Optional Aliyun OCR adapter with a safe manual-entry fallback."""

import re
from dataclasses import dataclass

from app.core.config import settings


@dataclass(frozen=True)
class OCRResult:
    text: str
    provider: str


def is_configured() -> bool:
    return bool(settings.aliyun_ocr_access_key_id and settings.aliyun_ocr_access_key_secret)


def recognize_image(content: bytes) -> OCRResult:
    """Call Aliyun only when credentials exist; callers can fall back on errors."""
    if not is_configured():
        raise RuntimeError("阿里云 OCR 尚未配置")
    try:
        from alibabacloud_ocr_api20210707.client import Client
        from alibabacloud_ocr_api20210707.models import RecognizeGeneralRequest
        from alibabacloud_tea_openapi.models import Config
    except ImportError as exc:
        raise RuntimeError("服务器尚未安装阿里云 OCR SDK") from exc

    config = Config(
        access_key_id=settings.aliyun_ocr_access_key_id,
        access_key_secret=settings.aliyun_ocr_access_key_secret,
        endpoint=settings.aliyun_ocr_endpoint,
    )
    client = Client(config)
    request = RecognizeGeneralRequest(body=content)
    response = client.recognize_general(request)
    body = getattr(response, "body", None)
    data = getattr(body, "data", None)
    text = getattr(data, "content", None) if data else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("阿里云 OCR 未返回文字")
    return OCRResult(text=text, provider="aliyun-general")


def parse_score_text(text: str) -> dict:
    """Extract common score-sheet fields; every value remains parent-confirmable."""
    labels = {
        "chinese": r"语文",
        "math": r"数学",
        "english": r"英语",
        "physics": r"物理",
        "politics": r"(?:道法|政治)",
        "history": r"历史",
        "chemistry": r"化学",
        "biology": r"生物",
        "geography": r"地理",
        "pe": r"体育",
    }
    scores: dict[str, float] = {}
    for key, label in labels.items():
        match = re.search(rf"{label}\s*[：: ]\s*(\d+(?:\.\d+)?)", text)
        if match:
            scores[key] = float(match.group(1))
    scores.setdefault("pe", 60.0)
    academic = [value for key, value in scores.items() if key != "pe"]
    total_match = re.search(r"总分\s*[：: ]\s*(\d+(?:\.\d+)?)", text)
    exam_match = re.search(r"([^\n]*(?:月考|期中|期末|模考|测验|考试)[^\n]*)", text)
    grade_rank = re.search(r"年级\s*(?:第\s*)?(\d+)\s*名", text)
    class_rank = re.search(r"班(?:级)?\s*(?:第\s*)?(\d+)\s*名", text)
    grade_size = re.search(r"年级\s*(?:共|总)?\s*(\d+)\s*人", text)
    return {
        "name": exam_match.group(1).strip() if exam_match else "",
        "total_score": float(total_match.group(1)) if total_match else round(sum(academic) + scores["pe"], 1),
        "scores": scores,
        "physical_score": scores["pe"],
        "class_rank": int(class_rank.group(1)) if class_rank else None,
        "grade_rank": int(grade_rank.group(1)) if grade_rank else None,
        "grade_size": int(grade_size.group(1)) if grade_size else None,
    }
