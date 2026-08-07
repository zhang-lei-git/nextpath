#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { validateInput, loadJson } = require('./validate-input');

const SKILL_ROOT = path.resolve(__dirname, '..');
const TEMPLATE_PATH = path.join(SKILL_ROOT, 'skill_assets', 'report-template.html');
const CSS_PATH = path.join(SKILL_ROOT, 'skill_assets', 'report.css');
const CHART_PATH = path.join(SKILL_ROOT, 'skill_assets', 'chart-runtime.js');

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function rich(value) {
  return String(value ?? '');
}

function attr(value) {
  return escapeHtml(value);
}

function sectionHead(number, label, title, lead = '') {
  return `<div class="sec-head"><div class="sec-num"><small>PART</small>${number} · ${escapeHtml(label)}</div><div><h2>${escapeHtml(title)}</h2>${lead ? `<p class="lead">${escapeHtml(lead)}</p>` : ''}</div></div>`;
}

function renderHero(report) {
  const meta=report.meta;
  const totalNote=meta.totalNote ? `（${escapeHtml(meta.totalNote)}）` : '';
  const scoreLabel=meta.scoreLabel || '中考';
  return `<header class="hero">
    <div class="eyebrow">${escapeHtml(meta.year)} · ${escapeHtml(meta.eyebrow)}</div>
    <h1>${escapeHtml(meta.title)}</h1>
    <p>${escapeHtml(meta.description)}</p>
    <div class="hero-meta">
      <span>学生：<b>${escapeHtml(meta.studentLabel)}</b></span>
      <span>规划通道：<b>${escapeHtml(meta.admissionLabel)}</b></span>
      <span>${escapeHtml(scoreLabel)}：<b>${escapeHtml(meta.reportedTotal)} 分</b>${totalNote}</span>
      <span>目标：<b>${escapeHtml(meta.targetLabel)}</b></span>
    </div>
  </header>`;
}

function renderGlance(report) {
  const toneClass={blue:'',teal:'k2',green:'k3',red:'k4'};
  const kpis=report.glance.kpis.map((item,index)=>`<div class="kpi ${toneClass[item.tone] || `k${Math.min(index+1,4)}`}">
    <div class="kpi-label">${escapeHtml(item.label)}</div><div class="kpi-value">${escapeHtml(item.value)}</div><div class="kpi-note">${escapeHtml(item.note)}</div></div>`).join('');
  const conditions=report.glance.conditions.map(item=>`<div class="trio ${attr(item.tone)}"><b>${escapeHtml(item.label)}</b>${escapeHtml(item.text)}</div>`).join('');
  return `<div class="glance" id="glance"><span class="glance-tag">一页速览 · 给家长的核心信息</span>
    <p class="glance-verdict">${rich(report.glance.verdictHtml)}</p>
    <div class="glance-grid">${kpis}</div><div class="glance-trio">${conditions}</div></div>`;
}

function renderNav() {
  const report = arguments[0] || {};
  const schoolLabel = report.school?.navLabel || '学校出口';
  const pathLabel = report.path?.navLabel || '目标路径';
  return `<nav class="topnav" aria-label="报告章节导航"><a href="#glance">速览</a><a href="#conclusion">01 当前判断</a><a href="#data">02 成绩变化</a><a href="#subjects">03 学科情况</a><a href="#school">04 ${escapeHtml(schoolLabel)}</a><a href="#path">05 ${escapeHtml(pathLabel)}</a><a href="#action">06 下一步</a><a href="#decisions">07 家长关注</a></nav>`;
}

function renderConclusion(report) {
  const cards=report.conclusion.cards.map(card=>`<div class="panel ${attr(card.tone)}"><h3>${card.icon ? `<span class="ico">${escapeHtml(card.icon)}</span>` : ''}${escapeHtml(card.title)}</h3><p style="margin-bottom:0">${escapeHtml(card.text)}</p></div>`).join('');
  return `<section id="conclusion">${sectionHead('01','结论',report.conclusion.title)}<div class="verdict">${rich(report.conclusion.verdictHtml)}</div><div class="three-col" style="margin-top:20px">${cards}</div><div class="takeaway"><span>${rich(report.conclusion.takeawayHtml)}</span></div></section>`;
}

function renderData(report) {
  const subjects=report.subjects.filter(subject=>subject.table !== false);
  const comparable=report.data.exams.filter(exam=>exam.comparable !== false);
  const ranked=comparable.filter(exam=>typeof exam.rank === 'number');
  const bestRank=ranked.length ? Math.min(...ranked.map(exam=>exam.rank)) : null;
  const worstRank=ranked.length ? Math.max(...ranked.map(exam=>exam.rank)) : null;
  const head=subjects.map(subject=>`<th>${escapeHtml(subject.name)}</th>`).join('');
  const rows=report.data.exams.map(exam=>{
    const cells=subjects.map(subject=>`<td>${exam.scores?.[subject.key] ?? '—'}</td>`).join('');
    let rank='未提供';
    if (typeof exam.rank === 'number') {
      const cls=exam.rank===bestRank?'up':exam.rank===worstRank?'down':'';
      rank=`<span class="${cls}">${exam.rank}/${report.data.classSize}</span>`;
    }
    return `<tr class="${exam.final ? 'highlight' : ''}"><td>${escapeHtml(exam.display)}</td>${cells}<td>${rank}</td></tr>`;
  }).join('');
  const sectionTitle=report.data.sectionTitle || '模考与中考成绩全景';
  const sectionLead=report.data.sectionLead || '持续记录每次成绩和排名，观察变化。';
  return `<section id="data">${sectionHead('02','数据',sectionTitle,sectionLead)}
    <div class="chart-wrap"><div class="chart-title"><strong>核心学科成绩变化</strong><span>最右侧为最近一次考试</span></div><div class="legend" id="scoreLegend"></div><svg id="scoreChart" viewBox="0 0 980 400" role="img" aria-label="历次考试学科成绩变化"></svg></div>
    <div class="two-col" style="margin-top:22px"><div class="chart-wrap"><div class="chart-title"><strong>班级名次趋势</strong><span>${report.data.classSize} 人班 · 越靠上越好</span></div><svg id="rankChart" viewBox="0 0 560 380" role="img" aria-label="历次考试班级名次趋势"></svg></div>
    <div class="panel"><h3>年级排名</h3><p>${rich(report.data.rankNarrativeHtml)}</p><div class="panel blue" style="margin-top:14px;padding:16px 18px"><strong>成绩记录</strong><p style="margin:6px 0 0;font-size:14.5px">${rich(report.data.inferenceHtml)}</p></div></div></div>
    <div class="table-scroll" style="margin-top:22px"><table><thead><tr><th>考试</th>${head}<th>名次</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${report.data.auxiliaryNote ? `<p class="small muted" style="margin-top:10px">${escapeHtml(report.data.auxiliaryNote)}</p>` : ''}
    <div class="takeaway"><span>${rich(report.data.takeawayHtml)}</span></div></section>`;
}

function renderSubjects(report) {
  const profile=report.subjects.filter(subject=>subject.profile !== false).map(subject=>({...subject,rate:subject.finalScore/subject.max*100})).sort((a,b)=>b.rate-a.rate);
  const toneColor={high:'linear-gradient(90deg,#37a06b,#2e8b57)',mid:'linear-gradient(90deg,#d99a3f,#c9872f)',risk:'linear-gradient(90deg,#cd6350,#c0503f)'};
  const rows=profile.map((subject,index)=>`<div class="subject-row"><span class="rank-badge r${Math.min(index+1,6)}">${index+1}</span><span class="subject-name">${escapeHtml(subject.name)}</span><div class="bar"><span style="width:${Math.min(100,subject.rate).toFixed(1)}%;background:${toneColor[subject.tone] || toneColor.mid}"></span></div><span class="subject-score">${subject.rate.toFixed(1)}%</span></div>`).join('');
  const actions=profile.filter(subject=>subject.role && subject.action).map(subject=>`<tr><td><strong>${escapeHtml(subject.name)}</strong></td><td><span class="tag ${attr(subject.tone)}">${escapeHtml(subject.role)}</span></td><td style="white-space:normal">${escapeHtml(subject.action)}</td></tr>`).join('');
  return `<section id="subjects">${sectionHead('03','学科',report.subjectSectionTitle || '学科结构与资源配置')}
    <div class="two-col"><div class="panel"><h3>${escapeHtml(report.subjectPanelTitle || '最后一次模考得分率排行')}</h3><div class="subject-list">${rows}</div><p class="small muted" style="margin-top:16px;margin-bottom:0">得分率按各科已知满分折算，不能直接比较不同满分的原始分数。</p></div><div class="panel"><h3>分科行动判断</h3><table><tbody>${actions}</tbody></table></div></div>
    <div class="takeaway"><span>${rich(report.subjectTakeawayHtml || '')}</span></div></section>`;
}

function renderEvidence(item) {
  const label={official:'官方可核验',media:'媒体转述',third_party:'第三方整理',missing:'公开缺失'}[item.level] || item.level;
  const tone={official:'high',media:'mid',third_party:'mid',missing:'risk'}[item.level] || 'mid';
  const rowStyle=item.level==='missing'?' style="background:var(--soft-red);border-color:#f0d2cb"':'';
  const metricStyle=item.level==='missing'?' style="color:var(--red)"':'';
  const title=item.url?`<a href="${attr(item.url)}" target="_blank" rel="noreferrer"><strong>${escapeHtml(item.title)}</strong></a>`:`<strong>${escapeHtml(item.title)}</strong>`;
  return `<div class="evidence-row"${rowStyle}><div><span class="tag ${tone}">${label}</span></div><div class="evidence-value"${metricStyle}>${escapeHtml(item.metric)}</div><div>${title}<div class="evidence-source">${escapeHtml(item.detail)}</div></div></div>`;
}

function renderPositionPanel(position) {
  return `<h3>${escapeHtml(position.title || '目标位置')}</h3><div class="verdict" style="font-size:15px;padding:16px 18px;margin-top:12px">${rich(position.estimateHtml || '')}</div>`;
}

function renderSchool(report) {
  const entrance=report.school.entrance;
  const evidence=report.school.evidence.map(renderEvidence).join('');
  const marker=(type, value, label, prefix='') => value === null || value === undefined || value === '' ? '' : `<div class="entrance-marker ${type}"><strong>${escapeHtml(prefix)}${escapeHtml(value)}</strong><small>${escapeHtml(label)}</small></div>`;
  const gapNotes=[entrance.cityGapLabel, entrance.schoolGapLabel].filter(Boolean).map((note,index)=>`<span class="gap-note${index ? ' amber' : ''}">${escapeHtml(note)}</span>`).join('&nbsp;');
  const scaleNote=entrance.note ? `<p class="small muted" style="margin:12px 4px 0">${escapeHtml(entrance.note)}</p>` : '';
  const positionPanel=report.school.position ? renderPositionPanel(report.school.position) : `<h3>${escapeHtml(report.school.entranceTitle || `${report.meta.year} 入口位置`)}</h3><div class="entrance-scale" aria-label="招生政策与当前位置参照"><div class="entrance-line"></div>${marker('city', entrance.cityLine, entrance.cityLabel)}${marker('school', entrance.schoolLine, entrance.schoolLabel, '约')}${marker('student', entrance.studentScore, entrance.studentLabel || '学生')}</div>${gapNotes}${scaleNote}`;
  return `<section id="school">${sectionHead('04','学校',report.school.title,report.school.lead)}<div class="two-col"><div class="panel">${positionPanel}</div>
    <div class="panel blue"><h3>${escapeHtml(report.school.environmentTitle || '学校培养环境')}</h3>${rich(report.school.environmentHtml)}</div></div>
    ${evidence ? `<div class="evidence-list" style="margin-top:22px">${evidence}</div>` : ''}<div class="panel amber" style="margin-top:18px"><h3>${escapeHtml(report.school.interpretationTitle || '当前关注')}</h3><p style="margin-bottom:0">${rich(report.school.interpretationHtml)}</p></div><div class="takeaway"><span>${rich(report.school.takeawayHtml)}</span></div></section>`;
}

function renderPath(report) {
  const milestones=report.path.milestones.map(item=>`<div class="path-step ${attr(item.tone)}"><div class="path-time">${escapeHtml(item.time)}</div><div class="path-goal">${rich(item.goalHtml)}</div></div>`).join('');
  const scenarios=report.path.scenarios.map(item=>`<div class="risk-cell ${attr(item.tone)}"><strong><span class="dot"></span>${escapeHtml(item.title)}</strong>${escapeHtml(item.text)}</div>`).join('');
  return `<section id="path">${sectionHead('05','路径',report.path.title)}<div class="pathway">${milestones}</div><div class="risk-matrix" style="margin-top:24px">${scenarios}</div><div class="takeaway"><span>${rich(report.path.takeawayHtml)}</span></div></section>`;
}

function checklist(items) {
  return `<ul class="checklist">${items.map(item=>`<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}

function renderAction(report) {
  const timeline=report.action.timeline.map(item=>`<div class="timeline-item"><span class="timeline-time">${escapeHtml(item.time)}</span><div><strong>${escapeHtml(item.title)}</strong></div><p>${escapeHtml(item.text)}</p></div>`).join('');
  return `<section id="action">${sectionHead('06','行动',report.action.title)}<div class="two-col"><div class="timeline">${timeline}</div><div><div class="panel blue"><h3>${escapeHtml(report.action.observationTitle)}</h3>${checklist(report.action.observationItems)}</div><div class="panel" style="margin-top:14px"><h3>${escapeHtml(report.action.courseCheckTitle)}</h3>${checklist(report.action.courseCheckItems)}${report.action.courseCheckNote?`<p class="small muted" style="margin-top:12px;margin-bottom:0">${escapeHtml(report.action.courseCheckNote)}</p>`:''}</div></div></div><div class="takeaway"><span>${rich(report.action.takeawayHtml)}</span></div></section>`;
}

function renderDecisions(report) {
  const cards=report.decisions.cards.map(card=>`<div class="panel"><h3>${card.icon?`<span class="ico">${escapeHtml(card.icon)}</span>`:''}${escapeHtml(card.title)}</h3><p style="margin-bottom:0">${escapeHtml(card.text)}</p></div>`).join('');
  return `<section id="decisions">${sectionHead('07','决策',report.decisions.title)}<div class="three-col">${cards}</div><div class="verdict" style="margin-top:22px">${rich(report.decisions.finalVerdictHtml)}</div></section>`;
}

function renderSources(report) {
  return '';
}

function renderBody(report) {
  return `<div class="report">${renderHero(report)}${renderGlance(report)}${renderNav(report)}<main>${renderConclusion(report)}${renderData(report)}${renderSubjects(report)}${renderSchool(report)}${renderPath(report)}${renderAction(report)}${renderDecisions(report)}</main><footer class="footer">${escapeHtml(report.footer)}</footer></div>`;
}

function buildReport(report) {
  const validation=validateInput(report);
  if (validation.errors.length) throw new Error(`Input validation failed:\n${validation.errors.map(error=>`- ${error}`).join('\n')}`);
  const template=fs.readFileSync(TEMPLATE_PATH,'utf8');
  const css=fs.readFileSync(CSS_PATH,'utf8');
  const chartRuntime=fs.readFileSync(CHART_PATH,'utf8');
  const html=template
    .replace('{{DOCUMENT_TITLE}}',escapeHtml(report.meta.title))
    .replace('{{REPORT_CSS}}',css)
    .replace('{{REPORT_BODY}}',renderBody(report))
    .replace('{{REPORT_DATA_JSON}}',JSON.stringify(report).replaceAll('</script>','<\\/script>'))
    .replace('{{CHART_RUNTIME}}',chartRuntime);
  return { html, validation };
}

if (require.main === module) {
  const [inputPath, outputPath] = process.argv.slice(2);
  if (!inputPath || !outputPath) {
    console.error('Usage: node build-report.js <input.json> <output.html>');
    process.exit(2);
  }
  try {
    const report=loadJson(inputPath);
    const result=buildReport(report);
    fs.writeFileSync(outputPath,result.html,'utf8');
    for(const warning of result.validation.warnings) console.warn(`WARNING: ${warning}`);
    console.log(`Built report: ${path.resolve(outputPath)}`);
  } catch (error) {
    console.error(error.message);
    process.exit(1);
  }
}

module.exports = { buildReport, renderBody };
