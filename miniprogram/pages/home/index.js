const { request } = require('../../utils/request')

Page({
  data: {
    dashboard: null, home: null, firstScreen: null,
    loading: true, loadError: false
  },
  onShow() { this.loadDashboard() },
  async loadDashboard() {
    this.setData({ loading: true })
    try {
      const dashboard = await request({ path: '/dashboard' })
      const firstScreen = dashboard.first_screen || null
      this.setData({ dashboard, firstScreen, loadError: false })
      this.setData({ home: this.buildHomeView(dashboard) })
    } catch (_) {
      this.setData({ dashboard: null, home: null, firstScreen: null, loadError: true })
    } finally { this.setData({ loading: false }) }
  },
  buildHomeView(dashboard) {
    const forecast = dashboard.forecast
    if (!forecast) return null
    const current = forecast.current_snapshot || null
    const projection = (forecast.exam_outcomes || []).find((item) => item.key === 'steady') || forecast.reasonable_projection || null
    const compactSchools = (tiers) => {
      const names = []
      ;['reach', 'match', 'safe'].forEach((tier) => (tiers && tiers[tier] || []).forEach((name) => {
        if (!names.includes(name)) names.push(name)
      }))
      return names.slice(0, 4)
    }
    return {
      hasTarget: Boolean(dashboard.target_school),
      targetRelation: forecast.target_comparison && forecast.target_comparison.projected_relation,
      current,
      projection,
      currentSchools: compactSchools(current && current.school_tiers),
      projectionSchools: compactSchools(projection && projection.school_tiers),
      projectionRange: projection && projection.total_range && `${projection.total_range[0]}–${projection.total_range[1]}`,
      projectionRank: projection && projection.estimated_rank_range && projection.estimated_rank_range[0] > 0
        ? `全区第 ${projection.estimated_rank_range[0].toLocaleString()}–${projection.estimated_rank_range[1].toLocaleString()} 名`
        : '位次仍需补充信息后估算'
    }
  },
  retry() { this.loadDashboard() },
  goToEntry() {
    if (!this.data.dashboard.profile_complete) { wx.navigateTo({ url: '/pages/profile/index' }); return }
    wx.navigateTo({ url: '/pages/score-entry/index' })
  },
  goToAnalysis() { wx.navigateTo({ url: '/pages/analysis/index' }) },
  openSchool(event) { wx.navigateTo({ url: `/pages/school-detail/index?name=${encodeURIComponent(event.currentTarget.dataset.name)}` }) },
  goToScores() { wx.navigateTo({ url: '/pages/scores/index' }) },
  goToTrend() { wx.navigateTo({ url: '/pages/scores/index' }) },
  goToReports() { wx.navigateTo({ url: '/pages/reports/index' }) },
  goSchool(event) { wx.navigateTo({ url: `/pages/school-detail/index?name=${encodeURIComponent(event.currentTarget.dataset.name)}` }) },
  showProfile() { wx.navigateTo({ url: '/pages/profile/index' }) },
  completeLatestExam() {
    const latest = this.data.dashboard && this.data.dashboard.latest_exam
    if (latest) wx.navigateTo({ url: `/pages/score-entry/index?id=${latest.id}` })
  }
})
