const { request } = require('../../utils/request')

Page({
  data: { reports: [], loading: true },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true })
    try { this.setData({ reports: await request({ path: '/reports' }) }) }
    catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  open(event) { wx.navigateTo({ url: `/pages/report-web/index?id=${event.currentTarget.dataset.id}` }) }
})
