const { request } = require('../../utils/request')
Page({
  data: { name: '', facts: [], loading: true },
  async onLoad(options) {
    const name = decodeURIComponent(options.name || '')
    this.setData({ name })
    try {
      const result = await request({ path: `/data/consumer/schools/${encodeURIComponent(name)}`, data: { region: '西安', reference_year: 2026 } })
      this.setData({ facts: result.facts || [] })
    } catch (_) { wx.showToast({ title: '暂时无法读取学校信息', icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  }
})
