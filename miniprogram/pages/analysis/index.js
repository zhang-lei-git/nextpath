const { request } = require('../../utils/request')
Page({
  data: { forecast: null, latest: null, report: null, loading: true },
  async onLoad() {
    try {
      const result = await request({ path: '/dashboard' })
      this.setData({ forecast: result.forecast, latest: result.latest_exam, report: result.report })
    } catch (_) { wx.showToast({ title: '暂时无法获取分析', icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  goToEntry() { wx.navigateTo({ url: '/pages/score-entry/index' }) },
  goToReports() { wx.navigateTo({ url: '/pages/reports/index' }) }
})
