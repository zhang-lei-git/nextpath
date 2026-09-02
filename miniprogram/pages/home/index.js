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
    return {
      hasTarget: Boolean(dashboard.target_school),
      targetCurrent: forecast.target_comparison && forecast.target_comparison.current_relation,
      targetProjection: forecast.target_comparison && forecast.target_comparison.projected_relation,
      trend: (dashboard.trend || []).slice(-3)
    }
  },
  retry() { this.loadDashboard() },
  goToEntry() {
    if (!this.data.dashboard.profile_complete) { wx.navigateTo({ url: '/pages/profile/index' }); return }
    wx.navigateTo({ url: '/pages/score-entry/index' })
  },
  goToAnalysis() { wx.navigateTo({ url: '/pages/analysis/index' }) },
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
