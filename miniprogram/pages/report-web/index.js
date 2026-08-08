const { request } = require('../../utils/request')

Page({
  data: { report: null, loading: true, loadError: false },
  async onLoad(options) {
    this.reportId = options.id
    await this.loadReport()
  },
  async loadReport() {
    this.setData({ loading: true, loadError: false })
    try {
      const report = await request({ path: `/reports/${this.reportId}` })
      this.setData({ report, loadError: false })
    } catch (error) {
      this.setData({ report: null, loadError: true })
      wx.showToast({ title: error.message, icon: 'none' })
    } finally { this.setData({ loading: false }) }
  },
  retry() { this.loadReport() }
})
