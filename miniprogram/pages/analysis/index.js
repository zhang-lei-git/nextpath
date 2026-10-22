const { request } = require('../../utils/request')
Page({
  data: { forecast: null, latest: null, targetSchool: null, loading: true },
  async onLoad() {
    try {
      const result = await request({ path: '/dashboard' })
      this.setData({ forecast: result.forecast, latest: result.latest_exam, targetSchool: result.target_school })
    } catch (_) { wx.showToast({ title: '暂时无法获取分析', icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  goToEntry() { wx.navigateTo({ url: '/pages/score-entry/index' }) },
  goToReports() { wx.navigateTo({ url: '/pages/reports/index' }) }
  ,openSchool(event) { wx.navigateTo({ url: `/pages/school-detail/index?name=${encodeURIComponent(event.currentTarget.dataset.school)}` }) }
  ,openTier(event) {
    const schools = (this.data.forecast.current_snapshot.school_tiers[event.currentTarget.dataset.tier] || []).join('|')
    wx.navigateTo({ url: `/pages/school-detail/index?tier=${event.currentTarget.dataset.tier}&names=${encodeURIComponent(schools)}` })
  }
  ,openOutcomeSchools(event) {
    const outcome = (this.data.forecast.exam_outcomes || []).find((item) => item.key === event.currentTarget.dataset.key)
    const schools = outcome ? Object.values(outcome.school_tiers || {}).flat().join('|') : ''
    wx.navigateTo({ url: `/pages/school-detail/index?scope=${event.currentTarget.dataset.key}&names=${encodeURIComponent(schools)}` })
  }
})
