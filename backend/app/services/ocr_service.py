"""Optional Aliyun OCR adapter with a safe manual-entry fallback."""

import json
import re
from datetime import date
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
        connect_timeout=5000,
        read_timeout=20000,
    )
    client = Client(config)
    request = RecognizeGeneralRequest(body=content)
    response = client.recognize_general(request)
    body = getattr(response, "body", None)
    data = getattr(body, "data", None)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = None
    text = data.get("content") if isinstance(data, dict) else getattr(data, "content", None)
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
    exam_match = re.search(
        r"(?:(?:20\d{2}年)?\d{1,2}月)?(?:初[一二三]|九年级)?(?:第?[一二三四五六七八九十\d]+次)?"
        r"(?:[一二三]模(?:考试)?|模考[一二三四五六七八九十\d]*|月考|期中(?:考试)?|期末(?:考试)?|测验)", text
    )
    grade_rank = re.search(r"年级\s*(?:第\s*)?(\d+)\s*名", text)
    class_rank = re.search(r"班(?:级)?\s*(?:第\s*)?(\d+)\s*名", text)
    class_rank_value = int(class_rank.group(1)) if class_rank else None
    if class_rank_value is None:
        labelled = re.search(r"班级排名\s*[：:]?\s*(\d+)\b", text)
        above_labels = re.search(r"\b(\d+)\s+\d+(?:\.\d+)?\s+班级排名\s+总分", text)
        matched_rank = labelled or above_labels
        if matched_rank:
            class_rank_value = int(matched_rank.group(1))
    grade_size = re.search(r"年级\s*(?:共|总)?\s*(\d+)\s*人", text)
    exam_name = exam_match.group(0).strip() if exam_match else ""
    date_match = re.search(r"(?:考试时间|考试日期)\s*[：:]?\s*(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    exam_date = None
    if date_match:
        try:
            exam_date = date(*(int(part) for part in date_match.groups()))
        except ValueError:
            pass
    parsed = {
        "name": exam_name,
        "total_score": float(total_match.group(1)) if total_match else round(sum(academic) + scores["pe"], 1),
        "scores": scores,
        "physical_score": scores["pe"],
        "class_rank": class_rank_value,
        "grade_rank": int(grade_rank.group(1)) if grade_rank else None,
        "grade_size": int(grade_size.group(1)) if grade_size else None,
    }
    if exam_date:
        parsed["exam_date"] = exam_date
    return parsed
