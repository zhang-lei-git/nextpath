const { request } = require('../../utils/request')

Page({
  data: { reports: [], loading: true },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true })
    try {
      const reports = await request({ path: '/reports' })
      this.setData({ reports: reports.map((item) => ({
        ...item,
        display_date: item.period_key ? item.period_key.replace('-', '年') + '月' : item.created_at.slice(0, 10)
      })) })
    }
    catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  open(event) { wx.navigateTo({ url: `/pages/report-web/index?id=${event.currentTarget.dataset.id}` }) }
})
