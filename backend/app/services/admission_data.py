"""Versioned, auditable admissions reference data for the Xi'an launch sample."""

from dataclasses import dataclass


RANK_REFERENCE_YEAR = 2026
RANK_REFERENCE_SOURCE = "2026 年西安市城六区一分一段表（待官方复核）"
POLICY_SUMMARY = "城六区普通高中控制线 492 分；定向志愿每生限报 1 所。政策与计划发生变化时，只推送与孩子档案相关的更新。"

# Sparse points are deliberately interpolated. The report calls this an estimate, never an admission result.
RANK_POINTS: tuple[tuple[float, int], ...] = (
    (633, 86), (625, 916), (620, 2109), (615, 3690), (610, 5666),
    (605, 7859), (600, 10307), (595, 12795), (590, 15419), (585, 18064),
    (580, 20707), (575, 23295), (570, 26025), (565, 28539), (560, 30996),
    (555, 33389), (550, 35740), (545, 37939), (540, 40097), (535, 42167),
    (530, 44152), (525, 45984), (520, 47715), (515, 49304), (511, 50541),
)


@dataclass(frozen=True)
class SchoolReference:
    name: str
    estimated_line: float
    source: str


SCHOOL_REFERENCES = (
    SchoolReference("西北工业大学附属中学", 612, "2026 年公开预估区间 610-615，非官方录取线"),
    SchoolReference("西安铁一中", 607, "2026 年公开预估区间 605-610，非官方录取线"),
    SchoolReference("西安交通大学附属中学", 602, "2026 年公开预估区间 600-605，非官方录取线"),
    SchoolReference("西安高新第一中学", 600, "2026 年公开预估区间 598-603，非官方录取线"),
    SchoolReference("陕西师范大学附属中学", 597, "2026 年公开预估区间 595-600，非官方录取线"),
    SchoolReference("西安市第三中学", 587, "2026 年公开预估区间 585-590，非官方录取线"),
    SchoolReference("西安市第八十三中学", 575, "2026 年公开预估区间 570-580，非官方录取线"),
)


def estimate_city_rank(score: float) -> int | None:
    if score < RANK_POINTS[-1][0] or score > RANK_POINTS[0][0]:
        return None
    for high, low in zip(RANK_POINTS, RANK_POINTS[1:]):
        high_score, high_rank = high
        low_score, low_rank = low
        if low_score <= score <= high_score:
            ratio = (high_score - score) / (high_score - low_score)
            return round(high_rank + (low_rank - high_rank) * ratio)
    return RANK_POINTS[-1][1]


def find_school_reference(name: str | None) -> SchoolReference | None:
    if not name:
        return None
    normalized = name.replace(" ", "")
    return next((item for item in SCHOOL_REFERENCES if item.name.replace(" ", "") in normalized or normalized in item.name), None)
