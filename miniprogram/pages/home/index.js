const { request } = require('../../utils/request')

Page({
  data: { dashboard: null, home: null, loading: true, loadError: false },
  onShow() { this.loadDashboard() },
  async loadDashboard() {
    this.setData({ loading: true })
    try {
      const dashboard = await request({ path: '/dashboard' })
      this.setData({ dashboard, home: this.buildHomeView(dashboard), loadError: false })
    } catch (_) {
      this.setData({ dashboard: null, home: null, loadError: true })
    } finally { this.setData({ loading: false }) }
  },
  buildHomeView(dashboard) {
    const forecast = dashboard.forecast
    if (!forecast) return null
    return {
      current: { ...this.scenarioView(forecast.current_snapshot, '当前现状'), ...this.examMetrics(dashboard.latest_exam) },
      outcomes: (forecast.exam_outcomes || []).map((item) => this.scenarioView(item, item.title, item.key)),
      change: this.changeView(dashboard.change_summary),
      hasTarget: Boolean(dashboard.target_school),
      targetCurrent: forecast.target_comparison && forecast.target_comparison.current_relation,
      targetProjection: forecast.target_comparison && forecast.target_comparison.projected_relation,
      trend: (dashboard.trend || []).slice(-3)
    }
  },
  examMetrics(exam) {
    if (!exam) return {}
    return {
      scoreRate: exam.total_full_mark ? `${(exam.total_score / exam.total_full_mark * 100).toFixed(1)}%` : '—',
      gradeText: exam.grade_rank && exam.grade_size ? `年级第 ${exam.grade_rank} / ${exam.grade_size} 名` : '年级排名待补充'
    }
  },
  scenarioView(scenario, title, key = '') {
    if (!scenario) return null
    const tiers = scenario.school_tiers || {}
    const schoolTiers = [
      { label: '冲刺', schools: (tiers.reach || []).slice(0, 2) },
      { label: '匹配', schools: (tiers.match || []).slice(0, 2) },
      { label: '保底', schools: (tiers.safe || []).slice(0, 2) }
    ].filter((item) => item.schools.length)
    const scoreRange = scenario.total_range || []
    const rankRange = scenario.estimated_rank_range || []
    return {
      title,
      key,
      score: scoreRange[0] === scoreRange[1] ? scoreRange[0] : `${scoreRange[0]}–${scoreRange[1]}`,
      fullMark: scenario.total_full_mark,
      rankText: scenario.range_usable && rankRange[0] && rankRange[1]
        ? `预计全区第 ${this.formatNumber(rankRange[0])}–${this.formatNumber(rankRange[1])} 名`
        : '学校范围仍需继续观察',
      scope: scenario.school_scope || '学校范围仍需继续观察',
      clarity: scenario.clarity || '初步估算',
      hasSchoolTiers: schoolTiers.length > 0,
      schoolTiers
    }
  },
  changeView(change) {
    if (!change) return null
    const city = change.city_rank_delta
    return {
      comparable: change.comparable,
      total: change.total_delta === null ? '' : `${change.total_delta >= 0 ? '+' : ''}${change.total_delta}`,
      rate: change.score_rate_delta === null ? '' : `${change.score_rate_delta >= 0 ? '+' : ''}${change.score_rate_delta}%`,
      grade: change.grade_rank_delta === null ? '' : `${change.grade_rank_delta >= 0 ? '前移 ' : '后移 '}${Math.abs(change.grade_rank_delta)} 名`,
      city: city ? `全区位置${city[0] >= 0 ? '前移' : '后移'}约 ${Math.abs(city[0])}–${Math.abs(city[1])} 名` : '',
      scope: change.school_scope_changed ? '学校层次已变化' : '学校层次保持稳定'
    }
  },
  formatNumber(value) { return Number(value).toLocaleString('en-US') },
  retry() { this.loadDashboard() },
  goToEntry() {
    if (!this.data.dashboard.profile_complete) { wx.navigateTo({ url: '/pages/profile/index' }); return }
    wx.navigateTo({ url: '/pages/score-entry/index' })
  },
  goToAnalysis() { wx.navigateTo({ url: '/pages/analysis/index' }) },
  goToScores() { wx.navigateTo({ url: '/pages/scores/index' }) },
  goToReports() { wx.navigateTo({ url: '/pages/reports/index' }) },
  goSchool(event) { wx.navigateTo({ url: `/pages/school-detail/index?name=${encodeURIComponent(event.currentTarget.dataset.name)}` }) },
  showProfile() { wx.navigateTo({ url: '/pages/profile/index' }) },
  completeLatestExam() {
    const latest = this.data.dashboard && this.data.dashboard.latest_exam
    if (latest) wx.navigateTo({ url: `/pages/score-entry/index?id=${latest.id}` })
  }
})
