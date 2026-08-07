import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Exam, StudentProfile, StudentReport
from app.domain.schemas import AdmissionReport, Forecast, StudentReportRead
from app.repositories.report_repository import ReportRepository
from app.services.published_reference_data import PublishedReferenceData


SUBJECTS = (
    ("chinese", "语文", 120),
    ("math", "数学", 120),
    ("english", "英语", 120),
    ("physics", "物理", 80),
    ("history", "历史", 60),
    ("politics", "道法", 60),
    ("pe", "体育", 60),
)
REPORTING_ROOT = Path(__file__).resolve().parents[1] / "reporting"
REPORT_BUILDER = REPORTING_ROOT / "skill_scripts" / "build-report.js"


@dataclass(frozen=True)
class ReportContext:
    profile: StudentProfile
    exam: Exam
    exams: list[Exam]
    forecast: Forecast
    admission_report: AdmissionReport
    reference_data: PublishedReferenceData | None
    analysis_run_id: str | None


class StudentReportService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ReportRepository(session)

    async def publish(self, context: ReportContext) -> StudentReportRead:
        report_json = self._build_input(context)
        html_content = self._render_html(report_json)
        record = await self.repository.add(StudentReport(
            profile_id=context.profile.id,
            exam_id=context.exam.id,
            analysis_run_id=context.analysis_run_id,
            title=f"{context.exam.name}升学分析报告",
            report_json=report_json,
            html_content=html_content,
        ))
        await self.session.commit()
        return StudentReportRead.model_validate(record)

    async def list_for_profile(self, profile_id: str) -> list[StudentReportRead]:
        return [StudentReportRead.model_validate(item) for item in await self.repository.list_for_profile(profile_id)]

    async def get_for_profile(self, profile_id: str, report_id: str) -> StudentReport:
        report = await self.repository.get_for_profile(profile_id, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="未找到这份报告")
        return report

    async def get_public_html(self, report_id: str) -> StudentReport:
        report = await self.repository.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="未找到这份报告")
        return report

    def _build_input(self, context: ReportContext) -> dict:
        subjects = self._subjects(context.exam)
        exams = [self._exam_row(item, context.exam.id) for item in sorted(context.exams, key=lambda item: item.exam_date)]
        class_size = self._rank_size(context.exams)
        target = context.profile.target_school or "尚未设置目标高中"
        position = self._position_text(context.forecast)
        current_scenario = context.forecast.current_snapshot
        reasonable_scenario = context.forecast.reasonable_projection
        score_note = "" if sum(item["finalScore"] for item in subjects if item.get("table", True)) == context.exam.total_score else "科目分数未完整录入，总分以本次确认记录为准。"
        rank_note = (
            f"本次年级第 {context.exam.grade_rank}/{context.exam.grade_size} 名。"
            if context.exam.grade_rank and context.exam.grade_size else "下次可补全年级排名和年级人数。"
        )
        return {
            "meta": {
                "year": context.forecast.reference_year,
                "eyebrow": "中考升学位置分析",
                "title": f"{context.exam.name}升学分析报告",
                "description": "围绕目标高中，持续记录成绩与位置变化。",
                "studentLabel": "孩子",
                "admissionLabel": context.profile.junior_school or "初中信息待补充",
                "targetLabel": target,
                "reportedTotal": context.exam.total_score,
                "totalNote": score_note,
                "outputTitle": f"nextpath-{context.exam.id}",
                "scoreLabel": "本次学科总分",
            },
            "validation": {"allowTotalMismatch": True, "totalTolerance": 0.01},
            "glance": {
                "verdictHtml": f"<strong>{context.forecast.tier}</strong><br>目标：{target}",
                "kpis": [
                    {"label": "当前现状", "value": self._scenario_total(current_scenario), "note": "本次成绩", "tone": "blue"},
                    {"label": "合理预测", "value": self._scenario_total(reasonable_scenario), "note": "预计中考总分", "tone": "teal"},
                    {"label": "预测位置", "value": self._rank_value(context.forecast), "note": "全区位置", "tone": "teal"},
                    {"label": "目标差距", "value": self._gap_value(context.forecast), "note": target, "tone": "green"},
                ],
                "conditions": [
                    {"label": "已记录考试", "text": f"已保存 {len(exams)} 次成绩。", "tone": "good"},
                    {"label": "下一步", "text": "下一次成绩保存后将更新预测。", "tone": "good"},
                ],
            },
            "subjects": subjects,
            "data": {
                "classSize": class_size,
                "sectionTitle": "历次模考成绩与位置变化",
                "sectionLead": "持续记录每次成绩和排名，观察变化。",
                "exams": exams,
                "auxiliaryNote": score_note or None,
                "rankNarrativeHtml": rank_note,
                "inferenceHtml": "每一次成绩都会形成独立记录，方便比较变化。",
                "takeawayHtml": "持续记录成绩，预测会随最新情况更新。",
            },
            "conclusion": {
                "title": "当前升学判断",
                "verdictHtml": f"<strong>{context.forecast.tier}</strong><br>目标：{target}",
                "cards": [
                    {"title": "当前现状", "text": self._scenario_total(current_scenario), "tone": "blue", "icon": "1"},
                    {"title": "合理预测", "text": self._scenario_total(reasonable_scenario), "tone": "amber", "icon": "2"},
                    {"title": "目标差距", "text": self._gap_value(context.forecast), "tone": "green", "icon": "3"},
                ],
                "takeawayHtml": "下一次成绩保存后，预测将自动更新。",
            },
            "school": {
                "title": "目标高中",
                "lead": "围绕目标持续观察当前位置和差距。",
                "entrance": {
                    "cityLine": None, "cityLabel": "", "schoolLine": None, "schoolLabel": "",
                    "studentScore": context.exam.total_score, "studentLabel": "本次成绩",
                    "cityGapLabel": "", "schoolGapLabel": "", "note": "",
                },
                "environmentTitle": "孩子当前信息",
                "environmentHtml": f"<strong>目标：</strong>{target}<br><strong>初中：</strong>{context.profile.junior_school or '待补充'}",
                "evidence": [],
                "interpretationTitle": "当前关注",
                "interpretationHtml": f"合理预测下，目标差距为 {self._gap_value(context.forecast)}。",
                "takeawayHtml": "下一次成绩后继续关注差距变化。",
            },
            "path": {
                "title": "后续模考观察路径",
                "milestones": [
                    {"time": "本次", "goalHtml": position, "tone": "now"},
                    {"time": "下一次模考", "goalHtml": "补全<strong>年级排名与年级人数</strong>，观察位置变化。", "tone": "next"},
                    {"time": "志愿阶段", "goalHtml": "根据孩子成绩和目标，确定志愿组合。", "tone": "mid"},
                ],
                "scenarios": [
                    {"title": "位置前移", "text": "目标高中可进入更积极的观察范围。", "tone": "good"},
                    {"title": "位置波动", "text": "关注下一次成绩带来的变化。", "tone": "watch"},
                    {"title": "继续记录", "text": "保存成绩和年级排名。", "tone": "monitor"},
                ],
                "takeawayHtml": "每次新成绩都会形成新的快照，便于比较而不覆盖历史结论。",
            },
            "action": {
                "title": "下一阶段行动",
                "timeline": [
                    {"time": "现在", "title": "确认成绩记录", "text": "核对本次总分、年级排名和年级人数。"},
                    {"time": "下次考试前", "title": "聚焦科目结构", "text": "补录科目成绩，观察持续失分的学科。"},
                    {"time": "下一次考试后", "title": "更新预测", "text": "保存最新成绩，查看目标差距变化。"},
                ],
                "observationTitle": "这次重点观察",
                "observationItems": [f"目标：{target}", f"目标差距：{self._gap_value(context.forecast)}", rank_note],
                "courseCheckTitle": "家长需要保存的信息",
                "courseCheckItems": ["学校通知的成绩截图", "年级排名与年级人数"],
                "courseCheckNote": "成绩保存后可直接查看更新结果。",
                "takeawayHtml": "建议每次考试当天完成录入，保证分析基于完整、可核对的信息。",
            },
            "decisions": {
                "title": "家长决策原则",
                "cards": [
                    {"title": "看目标", "text": "目标高中是所有判断的参照。", "icon": "1"},
                    {"title": "看差距", "text": "关注当前现状和合理预测下的差距。", "icon": "2"},
                    {"title": "持续记录", "text": "每次成绩都会带来新的预测。", "icon": "3"},
                ],
                "finalVerdictHtml": "围绕目标，持续记录成绩，及时查看变化。",
            },
            "sources": [],
            "footer": "NextPath · 升学判断。",
        }

    @staticmethod
    def _subjects(exam: Exam) -> list[dict]:
        rows = []
        for key, name, full_mark in SUBJECTS:
            score = exam.scores.get(key)
            if isinstance(score, (int, float)) and 0 <= score <= full_mark:
                rows.append({
                    "key": key, "name": name, "max": full_mark, "finalScore": score,
                    "countInTotal": True, "tone": "mid", "role": "持续观察",
                    "action": "连续记录后再判断该科对总分位置的影响。",
                })
        while len(rows) < 3:
            index = len(rows) + 1
            rows.append({
                "key": f"pending_{index}", "name": "科目成绩待补充", "max": 1, "finalScore": 0,
                "countInTotal": False, "tone": "mid", "role": "", "action": "", "table": False, "profile": False,
            })
        return rows

    @staticmethod
    def _exam_row(exam: Exam, final_id: str) -> dict:
        valid_scores = {}
        max_by_key = {key: full_mark for key, _, full_mark in SUBJECTS}
        for key, score in exam.scores.items():
            if key in max_by_key and isinstance(score, (int, float)) and 0 <= score <= max_by_key[key]:
                valid_scores[key] = score
        return {
            "label": exam.name,
            "display": f"{exam.exam_date.year}.{exam.exam_date.month:02d} {exam.name}",
            "scores": valid_scores,
            "rank": exam.grade_rank if exam.grade_rank and exam.grade_size else None,
            "final": exam.id == final_id,
        }

    @staticmethod
    def _rank_size(exams: list[Exam]) -> int:
        sizes = [exam.grade_size for exam in exams if exam.grade_size]
        return max(sizes) if sizes else 1

    @staticmethod
    def _rank_value(forecast: Forecast) -> str:
        scenario = forecast.reasonable_projection
        if scenario and scenario.estimated_rank_range != (0, 0):
            return f"第 {scenario.estimated_rank_range[0]:,}–{scenario.estimated_rank_range[1]:,} 名"
        return "待补数据"

    @staticmethod
    def _scenario_total(scenario) -> str:
        if not scenario or not scenario.total_range or scenario.total_full_mark is None:
            return "待计算"
        low, high = scenario.total_range
        value = f"{low:g}" if low == high else f"{low:g}–{high:g}"
        return f"{value}/{scenario.total_full_mark:g}"

    @staticmethod
    def _gap_value(forecast: Forecast) -> str:
        comparison = forecast.target_comparison
        if comparison:
            gap = comparison.projected_gap_rank_range
            if not gap:
                return comparison.risk
            if gap[1] <= 0:
                return "已进入目标边界"
            if gap[0] <= 0:
                return "处于目标边界"
            return f"还需前移 {gap[0]:,}–{gap[1]:,} 名"
        if forecast.target_percentile_gap is not None:
            return f"{forecast.target_percentile_gap:.1f} 个百分点"
        if forecast.target_rank_gap is not None:
            return f"{forecast.target_rank_gap:,} 名"
        if forecast.target_gap is not None:
            return f"{forecast.target_gap:g} 分"
        return "待设目标"

    @staticmethod
    def _position_text(forecast: Forecast) -> str:
        if forecast.current_percentile is not None and forecast.estimated_percentile_range:
            lower, upper = forecast.estimated_percentile_range
            return f"当前预估处于全区前 {forecast.current_percentile:.1f}%，区间前 {lower:.1f}%–{upper:.1f}%。"
        return "当前缺少年级位置或可用历史参考曲线，暂不直接换算区域位次。"

    @staticmethod
    def _render_html(report_json: dict) -> str:
        if not REPORT_BUILDER.exists():
            raise RuntimeError("报告模板未安装")
        with tempfile.TemporaryDirectory(prefix="nextpath-report-") as directory:
            input_path = Path(directory) / "input.json"
            output_path = Path(directory) / "report.html"
            input_path.write_text(json.dumps(report_json, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                ["node", str(REPORT_BUILDER), str(input_path), str(output_path)],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if result.returncode:
                raise RuntimeError(f"报告生成失败：{result.stderr or result.stdout}")
            return output_path.read_text(encoding="utf-8")
