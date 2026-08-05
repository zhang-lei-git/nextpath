const state = { sources: [], evidence: [], facts: [], releases: [], publishedFacts: [], users: [], models: [], validations: [], activeStatus: "pending_review", selectedReleaseId: "", selectedModelId: "" };
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
function badge(status) { return `<span class="badge ${status}">${({pending_review:"待审核",approved:"已通过",rejected:"已拒绝"})[status] || status}</span>`; }

async function load() {
  const [sources, evidence, facts, releases, me, users, models] = await Promise.all([dataApi("sources"), dataApi("evidence"), dataApi("facts"), dataApi("releases"), api("auth/me"), api("users"), analysisApi("models")]);
  Object.assign(state, { sources, evidence, facts, releases, users, models, selectedReleaseId: state.selectedReleaseId || releases[0]?.id || "", selectedModelId: state.selectedModelId || models[0]?.id || "" });
  $("#currentUser").textContent = me.username;
  await loadPublishedFacts();
  await loadValidations();
  render();
}
async function loadPublishedFacts() { state.publishedFacts = state.selectedReleaseId ? await dataApi(`releases/${state.selectedReleaseId}/facts`) : []; }
async function loadValidations() { state.validations = state.selectedModelId ? await analysisApi(`models/${state.selectedModelId}/validations`) : []; }
function render() { renderOverview(); renderSources(); renderSelectors(); renderFacts(); renderPublishedFacts(); renderModels(); renderUsers(); }
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
  $("#factEvidence").innerHTML = `<option value="">请选择</option>${state.evidence.map((item) => `<option value="${item.id}">${text(item.title)}${item.source_name ? `（${text(item.source_name)}）` : ""}</option>`).join("")}`;
  $("#releaseSelect").innerHTML = state.releases.map((release) => `<option value="${release.id}">${text(release.name)} · ${release.fact_count} 条</option>`).join("");
  $("#releaseSelect").value = state.selectedReleaseId;
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
  $("#validationList").innerHTML = state.validations.length ? `<div class="panel-head"><h2>验证记录</h2><span>${state.validations.length} 次</span></div>${state.validations.map((item) => `<div class="list-item"><strong>${item.validation_year} 年 · ${item.sample_size} 个样本</strong><p>位次中位误差 ${item.median_absolute_rank_error ?? "-"} · 区间覆盖率 ${item.interval_coverage ?? "-"}</p>${item.notes ? `<p>${text(item.notes)}</p>` : ""}</div>`).join("")}` : '<div class="empty">暂无验证记录</div>';
}
function updateReleaseSelection() { const selected = $$(".release-check:checked").length; $("#releaseSelection").textContent = selected ? `已选择 ${selected} 条已审核数据，发布后家长端即可读取。` : "尚未选择可发布的数据。"; }
async function reviewFact(id, decision) { const note = window.prompt(decision === "approved" ? "审核说明（可留空）" : "拒绝原因", ""); if (note === null) return; try { await dataApi(`facts/${id}/review`, { method:"POST", body:JSON.stringify({decision,note}) }); notice("审核结果已保存"); await load(); } catch (error) { notice(error.message, true); } }
async function resetPassword(userId, username) { const password = window.prompt(`为 ${username} 设置新密码（至少 8 位）`); if (!password) return; try { await api(`users/${userId}/password`, { method:"POST", body:JSON.stringify({password}) }); notice("密码已重置"); await load(); } catch (error) { notice(error.message, true); } }
function formData(form) { return Object.fromEntries(new FormData(form).entries()); }
$("#sourceForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); if (!body.homepage_url) body.homepage_url=null; try { await dataApi("sources", {method:"POST",body:JSON.stringify(body)}); event.currentTarget.reset(); notice("数据来源已登记"); await load(); } catch(error) { notice(error.message,true); } });
$("#evidenceForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); ["url","excerpt"].forEach((key) => { if (!body[key]) body[key]=null; }); try { await dataApi("evidence", {method:"POST",body:JSON.stringify(body)}); event.currentTarget.reset(); notice("证据已保存，可继续录入候选数据"); await load(); } catch(error) { notice(error.message,true); } });
$("#factForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); try { body.scope = body.scope ? JSON.parse(body.scope) : {}; body.value = JSON.parse(body.value); body.reference_year = Number(body.reference_year); body.evidence_ids = [body.evidence_id]; delete body.evidence_id; await dataApi("facts", {method:"POST",body:JSON.stringify(body)}); event.currentTarget.reset(); notice("候选数据已提交，等待审核"); await load(); } catch(error) { notice(error.message.includes("JSON") ? "适用范围或数据内容不是有效 JSON" : error.message,true); } });
$("#releaseForm").addEventListener("submit", async (event) => { event.preventDefault(); const fact_ids=$$(".release-check:checked").map((box)=>box.value); if (!fact_ids.length) return notice("请先在“已通过”数据中选择要发布的内容",true); const body=formData(event.currentTarget); body.reference_year=Number(body.reference_year); body.fact_ids=fact_ids; if (!body.notes) body.notes=null; try { await dataApi("releases", {method:"POST",body:JSON.stringify(body)}); notice("版本已发布，家长端将读取这份数据"); await load(); } catch(error) { notice(error.message,true); } });
$("#userForm").addEventListener("submit", async (event) => { event.preventDefault(); try { await api("users", { method:"POST", body:JSON.stringify(formData(event.currentTarget)) }); event.currentTarget.reset(); notice("用户已添加"); await load(); } catch(error) { notice(error.message,true); } });
$("#modelForm").addEventListener("submit", async (event) => { event.preventDefault(); const modelId = $("#modelId").value; try { await analysisApi(`models/${modelId}`, { method:"PUT", body:JSON.stringify({ status:"active", parameters:{ rank_interval_ratio:Number($("#rankIntervalRatio").value), minimum_rank_interval:Number($("#minimumRankInterval").value) } }) }); notice("模型参数已保存，新分析将使用该参数"); await load(); } catch(error) { notice(error.message,true); } });
$("#validationForm").addEventListener("submit", async (event) => { event.preventDefault(); const body=formData(event.currentTarget); ["validation_year", "sample_size"].forEach((key) => body[key]=Number(body[key])); ["median_absolute_rank_error", "interval_coverage"].forEach((key) => body[key]=body[key] === "" ? null : Number(body[key])); if (!body.notes) body.notes=null; try { await analysisApi(`models/${state.selectedModelId}/validations`, { method:"POST", body:JSON.stringify(body) }); event.currentTarget.reset(); notice("验证记录已保存"); await load(); } catch(error) { notice(error.message,true); } });
$("#releaseSelect").addEventListener("change", async (event) => { state.selectedReleaseId=event.target.value; await loadPublishedFacts(); renderPublishedFacts(); });
$("#dataSearch").addEventListener("input", renderPublishedFacts); $("#dataType").addEventListener("change", renderPublishedFacts);
$$(".nav-item").forEach((button) => button.addEventListener("click", () => { $$(".nav-item").forEach((item)=>item.classList.toggle("active",item===button)); $$(".view").forEach((view)=>view.classList.toggle("active",view.id===button.dataset.view)); $("#pageTitle").textContent=titles[button.dataset.view]; }));
$$("[data-status]").forEach((button) => button.addEventListener("click", () => { state.activeStatus=button.dataset.status; $$("[data-status]").forEach((item)=>item.classList.toggle("selected",item===button)); renderFacts(); }));
$("#refreshButton").addEventListener("click", () => load().then(()=>notice("数据已刷新")).catch((error)=>notice(error.message,true)));
$("#logoutButton").addEventListener("click", async () => { await api("auth/logout", {method:"POST"}); window.location.assign("/login"); });
load().catch((error)=>notice(error.message,true));
