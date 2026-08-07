const state = { sources: [], evidence: [], facts: [], releases: [], publishedFacts: [], users: [], models: [], validations: [], calibrationSamples: [], ingestions: [], collectionJobs: [], collectionRuns: [], selectedCollectionRun: null, activeStatus: "pending_review", selectedReleaseId: "", selectedModelId: "" };
const titles = { overview: "数据总览", data: "基础数据", sources: "数据来源", capture: "采集录入", review: "审核发布", models: "分析模型", users: "用户管理" };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(`/api/${path}`, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  if (response.status === 401) { window.location.assign("/login"); throw new Error("登录已失效"); }
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "请求失败");
  return payload;
}
async function dataApi(path, options = {}) { return api(`data/${path}`, options); }
async function analysisApi(path, options = {}) { return api(`analysis/${path}`, options); }
function notice(message, error = false) { const node = $("#notice"); node.textContent = message; node.className = `notice${error ? " error" : ""}`; setTimeout(() => node.classList.add("hidden"), 4200); }
function text(value) { return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[char])); }
function formatDate(value) { return value ? new Date(typeof value === "number" ? value * 1000 : value).toLocaleString("zh-CN", { hour12:false }) : "-"; }
function badge(status) { return `<span class="badge ${status}">${({pending_review:"待审核",approved:"已通过",rejected:"已拒绝",running:"运行中",normalized:"已治理",unchanged:"无变化",failed:"失败",active:"运行中",paused:"已暂停"})[status] || status}</span>`; }
function collectionStatus(status) { return ({running:"运行中",pending_review:"待审核",normalized:"已治理",unchanged:"无变化",failed:"失败"})[status] || status; }
function triggerType(value) { return ({scheduled:"定时",manual:"手动",retry:"重试",reprocess:"重新治理"})[value] || value; }
function changeType(value) { return ({new:"首次采集",changed:"内容有变化",unchanged:"内容无变化"})[value] || value; }
function stepName(value) { return ({capture:"采集快照",extract:"提取内容",normalize:"治理标准化"})[value] || value; }

async function load() {
  const [sources, evidence, facts, releases, me, users, models, calibrationSamples, ingestions, collectionJobs, collectionRuns] = await Promise.all([dataApi("sources"), dataApi("evidence"), dataApi("facts"), dataApi("releases"), api("auth/me"), api("users"), analysisApi("models"), analysisApi("calibration-samples"), dataApi("ingestions"), dataApi("collection-jobs"), dataApi("collection-runs")]);
  Object.assign(state, { sources, evidence, facts, releases, users, models, calibrationSamples, ingestions, collectionJobs, collectionRuns, selectedReleaseId: state.selectedReleaseId || releases[0]?.id || "", selectedModelId: state.selectedModelId || models[0]?.id || "" });
  $("#currentUser").textContent = me.username;
  await loadPublishedFacts();
  await loadValidations();
  render();
}
async function loadPublishedFacts() { state.publishedFacts = state.selectedReleaseId ? await dataApi(`releases/${state.selectedReleaseId}/facts`) : []; }
async function loadValidations() { state.validations = state.selectedModelId ? await analysisApi(`models/${state.selectedModelId}/validations`) : []; }
function render() { renderOverview(); renderSources(); renderSelectors(); renderFacts(); renderPublishedFacts(); renderIngestions(); renderCollectionJobs(); renderCollectionRuns(); renderModels(); renderUsers(); }
function renderOverview() {
  const pending = state.facts.filter((fact) => fact.status === "pending_review").length;
  $("#metrics").innerHTML = [["数据来源",state.sources.length,"已登记"],["证据材料",state.evidence.length,"可追溯"],["待审核",pending,"暂未进入家长端"],["已发布版本",state.releases.length,"家长端可读取"]].map(([label,value,note]) => `<div class="metric"><span>${label}</span><strong>${value}</strong><small>${note}</small></div>`).join("");
  $("#releaseList").innerHTML = state.releases.length ? state.releases.slice(0,5).map((release) => `<div class="list-item"><strong>${text(release.name)}</strong><p>${text(release.region)} · ${release.reference_year} · ${release.fact_count} 条数据</p><p>${formatDate(release.published_at)}</p></div>`).join("") : '<div class="empty">还没有发布版本</div>';
  const pendingFacts = state.facts.filter((fact) => fact.status === "pending_review").slice(0,5);
  $("#pendingPreview").innerHTML = pendingFacts.length ? pendingFacts.map((fact) => `<div class="list-item"><strong>${text(fact.entity_name)} · ${text(fact.field)}</strong><p>${text(fact.fact_type)} · ${fact.reference_year} · ${badge(fact.status)}</p></div>`).join("") : '<div class="empty">没有待审核数据</div>';
}
function renderSources() { $("#sourceCount").textContent = `${state.sources.length} 个来源`; $("#sourceList").innerHTML = state.sources.length ? state.sources.map((source) => `<div class="list-item"><strong>${text(source.name)}</strong><p>${text(source.source_type)} · ${text(source.reliability)}${source.homepage_url ? ` · <a href="${text(source.homepage_url)}" target="_blank" rel="noreferrer">查看链接</a>` : ""}</p></div>`).join("") : '<div class="empty">请先登记第一个数据来源</div>'; }
function renderSelectors() {
  $("#evidenceSource").innerHTML = `<option value="">请选择</option>${state.sources.map((source) => `<option value="${source.id}">${text(source.name)}</option>`).join("")}`;
  $("#documentSource").innerHTML = `<option value="">未指定来源</option>${state.sources.map((source) => `<option value="${source.id}">${text(source.name)}</option>`).join("")}`;
  $("#collectionSource").innerHTML = `<option value="">未指定来源</option>${state.sources.map((source) => `<option value="${source.id}">${text(source.name)}</option>`).join("")}`;
  $("#factEvidence").innerHTML = `<option value="">请选择</option>${state.evidence.map((item) => `<option value="${item.id}">${text(item.title)}${item.source_name ? `（${text(item.source_name)}）` : ""}</option>`).join("")}`;
  $("#releaseSelect").innerHTML = state.releases.map((release) => `<option value="${release.id}">${text(release.name)} · ${release.fact_count} 条</option>`).join("");
  $("#releaseSelect").value = state.selectedReleaseId;
}
function renderIngestions() {
  $("#ingestionCount").textContent = `${state.ingestions.length} 份`;
  $("#ingestionList").innerHTML = state.ingestions.length ? state.ingestions.slice(0,8).map((item) => `<div class="list-item"><strong>${text(item.title)}</strong><p>${text(item.ingestion_type)} · ${text(item.status)} · ${formatDate(item.created_at)}</p>${item.suggested_facts?.length ? `<p>待治理提示：${text(item.suggested_facts.map((fact) => fact.field).join("、"))}</p>` : ""}${item.error_message ? `<p>${text(item.error_message)}</p>` : ""}</div>`).join("") : '<div class="empty">上传文件或运行采集任务后，资料会在这里等待治理</div>';
}
function renderCollectionJobs() {
  $("#collectionCount").textContent = `${state.collectionJobs.length} 个`;
  $("#collectionList").innerHTML = state.collectionJobs.length ? state.collectionJobs.map((job) => `<div class="list-item"><div class="item-title-row"><strong>${text(job.name)}</strong>${badge(job.is_active ? "active" : "paused")}</div><p>${text(job.target_url)} · 每 ${job.interval_minutes} 分钟${job.owner ? ` · ${text(job.owner)}` : ""}</p><p>${job.last_status ? `最近：${text(collectionStatus(job.last_status))}` : "尚未运行"}${job.last_message ? ` · ${text(job.last_message)}` : ""}</p><div class="actions"><button class="button small secondary" data-run-collection="${job.id}">立即采集</button><button class="button small secondary" data-edit-job="${job.id}">编辑</button><button class="button small secondary" data-toggle-job="${job.id}" data-active="${job.is_active}">${job.is_active ? "暂停" : "启用"}</button></div></div>`).join("") : '<div class="empty">还没有采集任务</div>';
  $$("[data-run-collection]").forEach((button) => button.addEventListener("click", () => runCollection(button.dataset.runCollection)));
  $$("[data-edit-job]").forEach((button) => button.addEventListener("click", () => editCollectionJob(button.dataset.editJob)));
  $$("[data-toggle-job]").forEach((button) => button.addEventListener("click", () => toggleCollectionJob(button.dataset.toggleJob, button.dataset.active === "true")));
}
function renderCollectionRuns() {
  const jobNames = Object.fromEntries(state.collectionJobs.map((job) => [job.id, job.name]));
  $("#collectionRunCount").textContent = `${state.collectionRuns.length} 次`;
  $("#collectionRunList").innerHTML = state.collectionRuns.length ? state.collectionRuns.slice(0,20).map((run) => `<div class="run-row"><div><strong>${text(jobNames[run.job_id] || "采集任务")}</strong><p>${triggerType(run.trigger_type)} · ${formatDate(run.started_at || run.created_at)} · ${run.changed_count ? "发现变化" : "未发现变化"}</p></div><div class="run-status">${badge(run.status)}<button class="button small secondary" data-run-detail="${run.id}">查看日志</button></div></div>`).join("") : '<div class="empty">采集任务运行后，这里会显示完整记录</div>';
  $$("[data-run-detail]").forEach((button) => button.addEventListener("click", () => showCollectionRun(button.dataset.runDetail)));
  renderCollectionRunDetail();
}
function renderCollectionRunDetail() {
  const detail = state.selectedCollectionRun;
  const node = $("#collectionRunDetail");
  if (!detail) { node.innerHTML = '<div class="empty compact">选择一条运行记录查看采集和治理步骤</div>'; return; }
  const snapshots = detail.snapshots.map((snapshot) => { const attachments=snapshot.diff_summary?.attachments || []; const attachmentList=attachments.length ? `<div class="attachment-list">${attachments.map((item)=>`<p>${item.error ? "未保存" : "已保存"} · ${text(item.url)}${item.size ? ` · ${Math.ceil(item.size/1024)}KB` : ""}${item.error ? ` · ${text(item.error)}` : ""}</p>`).join("")}</div>` : ""; return `<div class="detail-block"><strong>原始快照 · ${text(changeType(snapshot.change_type))}</strong><p>${text(snapshot.final_url || snapshot.source_url)}</p><dl><div><dt>响应状态</dt><dd>${snapshot.response_status ?? "-"}</dd></div><div><dt>内容哈希</dt><dd class="mono">${text(snapshot.content_hash || "-")}</dd></div><div><dt>结构变化</dt><dd>${snapshot.diff_summary?.structure_changed ? "有" : "无"}</dd></div><div><dt>附件</dt><dd>${attachments.length} 个</dd></div></dl>${attachmentList}</div>`; }).join("");
  const steps = detail.steps.map((step) => `<div class="step-row"><span class="step-dot ${step.status}"></span><div><strong>${text(stepName(step.step_name))}</strong><p>${formatDate(step.started_at)} · ${step.status === "succeeded" ? "完成" : "失败"}${step.processor_version ? ` · ${text(step.processor_version)}` : ""}</p>${step.error_message ? `<p class="error-text">${text(step.error_message)}</p>` : ""}</div></div>`).join("");
  const retryButton = detail.status === "failed" ? `<button class="button small" id="retryRun">重试</button>` : "";
  const reprocessButton = detail.snapshots.length ? `<button class="button small secondary" id="reprocessRun">重新治理</button>` : "";
  node.innerHTML = `<div class="detail-head"><div><strong>${collectionStatus(detail.status)}</strong><p>${triggerType(detail.trigger_type)}触发 · ${formatDate(detail.started_at)} 至 ${formatDate(detail.finished_at)}</p></div><button class="icon-button" id="closeRunDetail" aria-label="关闭详情" title="关闭详情">×</button></div>${detail.error_message ? `<p class="error-text">${text(detail.error_message)}</p>` : ""}<div class="actions detail-actions">${retryButton}${reprocessButton}</div>${snapshots}<div class="step-list">${steps || '<div class="empty compact">暂无处理步骤</div>'}</div>`;
  $("#closeRunDetail").addEventListener("click", () => { state.selectedCollectionRun = null; renderCollectionRunDetail(); });
  $("#retryRun")?.addEventListener("click", () => retryCollectionRun(detail.id));
  $("#reprocessRun")?.addEventListener("click", () => reprocessCollectionRun(detail.id));
}
function renderFacts() {
  const visible = state.facts.filter((fact) => fact.status === state.activeStatus);
  $("#factList").innerHTML = visible.length ? visible.map((fact) => `<article class="fact-row"><div class="fact-top">${state.activeStatus === "approved" ? `<input class="release-check" type="checkbox" value="${fact.id}" aria-label="选择 ${text(fact.entity_name)}">` : ""}<div class="fact-main"><div class="fact-title">${text(fact.entity_name)} · ${text(fact.field)} ${badge(fact.status)}</div><div class="fact-meta">${text(fact.fact_type)} · ${text(fact.region)} · ${fact.reference_year} · ${text(fact.confidence)}</div><div class="fact-value">${text(JSON.stringify(fact.value, null, 2))}</div>${fact.status === "pending_review" ? `<div class="actions"><button class="button small" data-review="approved" data-id="${fact.id}">通过</button><button class="button small danger" data-review="rejected" data-id="${fact.id}">拒绝</button></div>` : fact.review_note ? `<div class="fact-meta">审核说明：${text(fact.review_note)}</div>` : ""}</div></div></article>`).join("") : '<div class="empty">当前没有这类数据</div>';
  $$("[data-review]").forEach((button) => button.addEventListener("click", () => reviewFact(button.dataset.id, button.dataset.review)));
  $$(".release-check").forEach((checkbox) => checkbox.addEventListener("change", updateReleaseSelection)); updateReleaseSelection();
}
function renderPublishedFacts() {
  const query = $("#dataSearch").value.trim().toLowerCase(); const type = $("#dataType").value;
  const visible = state.publishedFacts.filter((fact) => (type === "all" || fact.fact_type === type) && (!query || `${fact.entity_name} ${fact.field} ${JSON.stringify(fact.value)}`.toLowerCase().includes(query)));
  $("#publishedFactList").innerHTML = visible.length ? visible.map((fact) => `<article class="fact-row"><div class="fact-title">${text(fact.entity_name)} · ${text(fact.field)} <span class="badge approved">已发布</span></div><div class="fact-meta">${text(fact.fact_type)} · ${text(fact.region)} · ${fact.reference_year} · ${text(fact.confidence)}</div><div class="fact-value">${text(JSON.stringify(fact.value, null, 2))}</div></article>`).join("") : '<div class="empty">没有符合条件的已发布数据</div>';
}
function renderUsers() { $("#userList").innerHTML = state.users.map((user) => `<div class="list-item"><strong>${text(user.username)}</strong><p>创建于 ${formatDate(user.created_at)} · 最近修改 ${formatDate(user.updated_at)}</p><div class="actions"><button class="button small secondary" data-reset-user="${user.id}" data-name="${text(user.username)}">重置密码</button></div></div>`).join("") || '<div class="empty">还没有运营用户</div>'; $$("[data-reset-user]").forEach((button) => button.addEventListener("click", () => resetPassword(button.dataset.resetUser, button.dataset.name))); }
function renderModels() {
  const model = state.models.find((item) => item.id === state.selectedModelId);
  $("#modelList").innerHTML = state.models.map((item) => `<div class="list-item"><strong>${text(item.name)}</strong><p>${text(item.version)} · ${text(item.region)} · ${item.status === "active" ? "生效中" : "已停用"}</p><div class="actions"><button class="button small secondary" data-model-id="${item.id}">查看</button></div></div>`).join("") || '<div class="empty">尚未建立模型</div>';
  $$("[data-model-id]").forEach((button) => button.addEventListener("click", async () => { state.selectedModelId = button.dataset.modelId; await loadValidations(); renderModels(); }));
  if (!model) return;
  $("#modelId").value = model.id;
  $("#rankIntervalRatio").value = model.parameters.rank_interval_ratio ?? 0.06;
  $("#minimumRankInterval").value = model.parameters.minimum_rank_interval ?? 400;
  $("#schoolMappingMinSamples").value = model.parameters.school_mapping_min_samples ?? 15;
  $("#schoolMappingWeight").value = model.parameters.school_mapping_weight ?? 0.35;
  $("#scoreChannelUncertainty").value = model.parameters.score_channel_base_uncertainty_pp ?? 8;
  $("#rankPriorUncertainty").value = model.parameters.rank_channel_prior_uncertainty_pp ?? 12;
  $("#rankCalibratedUncertainty").value = model.parameters.rank_channel_calibrated_uncertainty_pp ?? 5;
  $("#rankChannelMinSamples").value = model.parameters.rank_channel_min_samples ?? 15;
  $("#fusionConflictThreshold").value = model.parameters.fusion_conflict_threshold_pp ?? 8;
  $("#fusionCorrelationInflation").value = model.parameters.fusion_correlation_inflation ?? 1.25;
  $("#scoreProjectionTrendWeight").value = model.parameters.score_projection_trend_weight ?? 0.6;
  $("#scoreProjectionMaxTrendPoints").value = model.parameters.score_projection_max_trend_points ?? 24;
  $("#scoreProjectionRangePoints").value = model.parameters.score_projection_range_points ?? 10;
  $("#difficultyStageUncertainty").value = JSON.stringify(model.parameters.difficulty_stage_uncertainty_pp ?? {}, null, 2);
  $("#schoolDifficultyProfiles").value = JSON.stringify(model.parameters.school_difficulty_profiles ?? {}, null, 2);
  $("#validationList").innerHTML = state.validations.length ? `<div class="panel-head"><h2>验证记录</h2><span>${state.validations.length} 次</span></div>${state.validations.map((item) => `<div class="list-item"><strong>${item.validation_year} 年 · ${item.sample_size} 个样本</strong><p>位次中位误差 ${item.median_absolute_rank_error ?? "-"} · 区间覆盖率 ${item.interval_coverage ?? "-"}</p>${item.notes ? `<p>${text(item.notes)}</p>` : ""}</div>`).join("")}` : '<div class="empty">暂无验证记录</div>';
  const pending = state.calibrationSamples.filter((item) => item.status === "pending_review").length;
  $("#calibrationSummary").textContent = `${state.calibrationSamples.length} 条样本 · ${pending} 条待审核`;
  $("#calibrationList").innerHTML = state.calibrationSamples.length ? state.calibrationSamples.map((item) => `<div class="list-item"><strong>${text(item.junior_school)} · ${text(item.assessment_stage)} · ${item.cohort_year}</strong><p>年级第 ${item.grade_rank}/${item.grade_size} 名 → 中考区域第 ${item.final_city_rank} 名${item.final_candidate_count ? `/${item.final_candidate_count}` : ""} · ${badge(item.status)}</p>${item.source_note ? `<p>${text(item.source_note)}</p>` : ""}${item.status === "pending_review" ? `<div class="actions"><button class="button small" data-calibration-review="approved" data-calibration-id="${item.id}">通过</button><button class="button small danger" data-calibration-review="rejected" data-calibration-id="${item.id}">拒绝</button></div>` : ""}</div>`).join("") : '<div class="empty">尚未录入校准样本</div>';
  $$("[data-calibration-review]").forEach((button) => button.addEventListener("click", () => reviewCalibrationSample(button.dataset.calibrationId, button.dataset.calibrationReview)));
}
function updateReleaseSelection() { const selected = $$(".release-check:checked").length; $("#releaseSelection").textContent = selected ? `已选择 ${selected} 条已审核数据，发布后家长端即可读取。` : "尚未选择可发布的数据。"; }
async function reviewFact(id, decision) { const note = window.prompt(decision === "approved" ? "审核说明（可留空）" : "拒绝原因", ""); if (note === null) return; try { await dataApi(`facts/${id}/review`, { method:"POST", body:JSON.stringify({decision,note}) }); notice("审核结果已保存"); await load(); } catch (error) { notice(error.message, true); } }
async function reviewCalibrationSample(id, decision) { const note = window.prompt(decision === "approved" ? "审核说明（可留空）" : "拒绝原因", ""); if (note === null) return; try { await analysisApi(`calibration-samples/${id}/review`, { method:"POST", body:JSON.stringify({decision,note}) }); notice("校准样本审核结果已保存"); await load(); } catch (error) { notice(error.message, true); } }
async function runCollection(id) { try { await dataApi(`collection-jobs/${id}/run`, { method:"POST" }); notice("采集完成，已进入待治理资料"); await load(); } catch(error) { notice(error.message,true); } }
async function showCollectionRun(id) { try { state.selectedCollectionRun = await dataApi(`collection-runs/${id}`); renderCollectionRunDetail(); } catch(error) { notice(error.message,true); } }
async function toggleCollectionJob(id, isActive) { try { await dataApi(`collection-jobs/${id}`, { method:"PATCH", body:JSON.stringify({is_active:!isActive}) }); notice(isActive ? "采集任务已暂停" : "采集任务已启用"); await load(); } catch(error) { notice(error.message,true); } }
function editCollectionJob(id) { const job=state.collectionJobs.find((item)=>item.id===id); if (!job) return; const form=$("#collectionForm"); form.elements.job_id.value=job.id; ["source_id","name","target_url","region","data_type","interval_minutes","extraction_hint"].forEach((key)=>{ form.elements[key].value=job[key] ?? ""; }); $("#collectionSubmit").textContent="保存修改"; $("#cancelCollectionEdit").classList.remove("hidden"); form.scrollIntoView({behavior:"smooth",block:"start"}); }
function resetCollectionForm() { const form=$("#collectionForm"); form.reset(); form.elements.job_id.value=""; form.elements.region.value="西安"; $("#collectionSubmit").textContent="保存任务"; $("#cancelCollectionEdit").classList.add("hidden"); }
async function retryCollectionRun(id) { try { await dataApi(`collection-runs/${id}/retry`, {method:"POST"}); state.selectedCollectionRun=null; notice("重试完成"); await load(); } catch(error) { notice(error.message,true); } }
async function reprocessCollectionRun(id) { const version=window.prompt("治理规则版本（留空则使用任务当前版本）", ""); if (version===null) return; try { await dataApi(`collection-runs/${id}/reprocess`, {method:"POST",body:JSON.stringify({governance_rule_version:version || null})}); state.selectedCollectionRun=null; notice("原始快照已重新治理"); await load(); } catch(error) { notice(error.message,true); } }
async function resetPassword(userId, username) { const password = window.prompt(`为 ${username} 设置新密码（至少 8 位）`); if (!password) return; try { await api(`users/${userId}/password`, { method:"POST", body:JSON.stringify({password}) }); notice("密码已重置"); await load(); } catch (error) { notice(error.message, true); } }
function formData(form) { return Object.fromEntries(new FormData(form).entries()); }
$("#sourceForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); if (!body.homepage_url) body.homepage_url=null; try { await dataApi("sources", {method:"POST",body:JSON.stringify(body)}); event.currentTarget.reset(); notice("数据来源已登记"); await load(); } catch(error) { notice(error.message,true); } });
$("#evidenceForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); ["url","excerpt"].forEach((key) => { if (!body[key]) body[key]=null; }); try { await dataApi("evidence", {method:"POST",body:JSON.stringify(body)}); event.currentTarget.reset(); notice("证据已保存，可继续录入候选数据"); await load(); } catch(error) { notice(error.message,true); } });
$("#documentForm").addEventListener("submit", async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); if (!form.get("source_id")) form.delete("source_id"); try { const response = await fetch("/api/data/ingestions/documents", { method:"POST", body:form }); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || "上传失败"); event.currentTarget.reset(); notice("资料已保存，等待治理"); await load(); } catch(error) { notice(error.message,true); } });
$("#collectionForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); const jobId=body.job_id; delete body.job_id; body.interval_minutes=Number(body.interval_minutes); if (!body.source_id) body.source_id=null; if (!body.region) body.region=null; if (!body.data_type) body.data_type=null; if (!body.extraction_hint) body.extraction_hint=null; try { await dataApi(jobId ? `collection-jobs/${jobId}` : "collection-jobs", {method:jobId ? "PATCH" : "POST",body:JSON.stringify(body)}); resetCollectionForm(); notice(jobId ? "采集任务已更新" : "采集任务已保存"); await load(); } catch(error) { notice(error.message,true); } });
$("#cancelCollectionEdit").addEventListener("click", resetCollectionForm);
$("#factForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); try { body.scope = body.scope ? JSON.parse(body.scope) : {}; body.value = JSON.parse(body.value); body.reference_year = Number(body.reference_year); body.evidence_ids = [body.evidence_id]; delete body.evidence_id; await dataApi("facts", {method:"POST",body:JSON.stringify(body)}); event.currentTarget.reset(); notice("候选数据已提交，等待审核"); await load(); } catch(error) { notice(error.message.includes("JSON") ? "适用范围或数据内容不是有效 JSON" : error.message,true); } });
$("#releaseForm").addEventListener("submit", async (event) => { event.preventDefault(); const fact_ids=$$(".release-check:checked").map((box)=>box.value); if (!fact_ids.length) return notice("请先在“已通过”数据中选择要发布的内容",true); const body=formData(event.currentTarget); body.reference_year=Number(body.reference_year); body.fact_ids=fact_ids; if (!body.notes) body.notes=null; try { await dataApi("releases", {method:"POST",body:JSON.stringify(body)}); notice("版本已发布，家长端将读取这份数据"); await load(); } catch(error) { notice(error.message,true); } });
$("#userForm").addEventListener("submit", async (event) => { event.preventDefault(); try { await api("users", { method:"POST", body:JSON.stringify(formData(event.currentTarget)) }); event.currentTarget.reset(); notice("用户已添加"); await load(); } catch(error) { notice(error.message,true); } });
$("#modelForm").addEventListener("submit", async (event) => { event.preventDefault(); const modelId = $("#modelId").value; try { const model = await analysisApi(`models/${modelId}`, { method:"PUT", body:JSON.stringify({ status:"active", parameters:{ rank_interval_ratio:Number($("#rankIntervalRatio").value), minimum_rank_interval:Number($("#minimumRankInterval").value), school_mapping_min_samples:Number($("#schoolMappingMinSamples").value), school_mapping_weight:Number($("#schoolMappingWeight").value), score_channel_base_uncertainty_pp:Number($("#scoreChannelUncertainty").value), rank_channel_prior_uncertainty_pp:Number($("#rankPriorUncertainty").value), rank_channel_calibrated_uncertainty_pp:Number($("#rankCalibratedUncertainty").value), rank_channel_min_samples:Number($("#rankChannelMinSamples").value), fusion_conflict_threshold_pp:Number($("#fusionConflictThreshold").value), fusion_correlation_inflation:Number($("#fusionCorrelationInflation").value), score_projection_trend_weight:Number($("#scoreProjectionTrendWeight").value), score_projection_max_trend_points:Number($("#scoreProjectionMaxTrendPoints").value), score_projection_range_points:Number($("#scoreProjectionRangePoints").value), difficulty_stage_uncertainty_pp:JSON.parse($("#difficultyStageUncertainty").value || "{}"), school_difficulty_profiles:JSON.parse($("#schoolDifficultyProfiles").value || "{}") } }) }); state.selectedModelId = model.id; notice("已生成新的模型版本，新分析将使用该版本"); await load(); } catch(error) { notice(error instanceof SyntaxError ? "难度配置不是有效 JSON" : error.message,true); } });
$("#calibrationForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); ["cohort_year", "grade_rank", "grade_size", "final_city_rank"].forEach((key) => body[key]=Number(body[key])); body.final_candidate_count = body.final_candidate_count ? Number(body.final_candidate_count) : null; if (!body.source_note) body.source_note=null; body.evidence_ids=[]; try { await analysisApi("calibration-samples", { method:"POST", body:JSON.stringify(body) }); event.currentTarget.reset(); notice("校准样本已提交，审核通过后才会参与分析"); await load(); } catch(error) { notice(error.message,true); } });
$("#validationForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); ["validation_year", "sample_size"].forEach((key) => body[key]=Number(body[key])); ["median_absolute_rank_error", "interval_coverage"].forEach((key) => body[key]=body[key] === "" ? null : Number(body[key])); if (!body.notes) body.notes=null; try { await analysisApi(`models/${state.selectedModelId}/validations`, { method:"POST", body:JSON.stringify(body) }); event.currentTarget.reset(); notice("验证记录已保存"); await load(); } catch(error) { notice(error.message,true); } });
$("#releaseSelect").addEventListener("change", async (event) => { state.selectedReleaseId=event.target.value; await loadPublishedFacts(); renderPublishedFacts(); });
$("#dataSearch").addEventListener("input", renderPublishedFacts); $("#dataType").addEventListener("change", renderPublishedFacts);
$$(".nav-item").forEach((button) => button.addEventListener("click", () => { $$(".nav-item").forEach((item)=>item.classList.toggle("active",item===button)); $$(".view").forEach((view)=>view.classList.toggle("active",view.id===button.dataset.view)); $("#pageTitle").textContent=titles[button.dataset.view]; }));
$$("[data-status]").forEach((button) => button.addEventListener("click", () => { state.activeStatus=button.dataset.status; $$("[data-status]").forEach((item)=>item.classList.toggle("selected",item===button)); renderFacts(); }));
$("#refreshButton").addEventListener("click", () => load().then(()=>notice("数据已刷新")).catch((error)=>notice(error.message,true)));
$("#logoutButton").addEventListener("click", async () => { await api("auth/logout", {method:"POST"}); window.location.assign("/login"); });
load().catch((error)=>notice(error.message,true));
