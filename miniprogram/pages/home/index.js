const { request } = require('../../utils/request')

Page({
  data: { dashboard: null, loading: true, loadError: false },
  onShow() { this.loadDashboard() },
  async loadDashboard() {
    this.setData({ loading: true })
    try {
      const dashboard = await request({ path: '/dashboard' })
      this.setData({ dashboard, loadError: false })
    } catch (_) {
      this.setData({ dashboard: null, loadError: true })
    } finally { this.setData({ loading: false }) }
  },
  retry() { this.loadDashboard() },
  goToEntry() {
    if (!this.data.dashboard.profile_complete) { wx.navigateTo({ url: '/pages/profile/index' }); return }
    wx.navigateTo({ url: '/pages/score-entry/index' })
  },
  goToAnalysis() { wx.navigateTo({ url: '/pages/analysis/index' }) },
  goToScores() { wx.navigateTo({ url: '/pages/scores/index' }) },
  showProfile() { wx.navigateTo({ url: '/pages/profile/index' }) }
})
