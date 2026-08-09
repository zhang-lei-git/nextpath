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
      current: this.scenarioView(forecast.current_snapshot, '当前现状'),
      projection: this.scenarioView(forecast.reasonable_projection, '中考预估'),
      hasTarget: Boolean(dashboard.target_school),
      targetCurrent: forecast.target_comparison && forecast.target_comparison.current_relation,
      targetProjection: forecast.target_comparison && forecast.target_comparison.projected_relation,
      actions: (dashboard.action_items || []).slice(0, 2),
      trend: (dashboard.trend || []).slice(-3)
    }
  },
  scenarioView(scenario, title) {
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
      score: scoreRange[0] === scoreRange[1] ? scoreRange[0] : `${scoreRange[0]}–${scoreRange[1]}`,
      fullMark: scenario.total_full_mark,
      rankText: scenario.range_usable && rankRange[0] && rankRange[1]
        ? `预计全区第 ${this.formatNumber(rankRange[0])}–${this.formatNumber(rankRange[1])} 名`
        : '学校范围仍需继续观察',
      scope: scenario.school_scope || '学校范围仍需继续观察',
      hasSchoolTiers: schoolTiers.length > 0,
      schoolTiers: schoolTiers.map((item) => ({ ...item, names: item.schools.join('、') }))
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
  showProfile() { wx.navigateTo({ url: '/pages/profile/index' }) },
  completeLatestExam() {
    const latest = this.data.dashboard && this.data.dashboard.latest_exam
    if (latest) wx.navigateTo({ url: `/pages/score-entry/index?id=${latest.id}` })
  }
})
