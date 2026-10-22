const { request } = require('../../utils/request')
Page({
  data: { name: '', facts: [], schools: [], tier: '', scope: '', loading: true },
  async onLoad(options) {
    const name = decodeURIComponent(options.name || '')
    const names = decodeURIComponent(options.names || '').split('|').filter(Boolean)
    this.setData({ name, tier: options.tier || '', scope: options.scope || '', schools: names.map((item) => ({ name: item, facts: [] })) })
    try {
      if (names.length) {
        const results = await Promise.all(names.map((school) => request({ path: `/data/consumer/schools/${encodeURIComponent(school)}`, data: { region: '西安', reference_year: 2026 } })))
        this.setData({ schools: names.map((school, index) => ({ name: school, facts: results[index].facts || [] })) })
      } else {
        const result = await request({ path: `/data/consumer/schools/${encodeURIComponent(name)}`, data: { region: '西安', reference_year: 2026 } })
        this.setData({ facts: result.facts || [] })
      }
    } catch (_) { wx.showToast({ title: '暂时无法读取学校信息', icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  openSchool(event) { wx.redirectTo({ url: `/pages/school-detail/index?name=${encodeURIComponent(event.currentTarget.dataset.name)}` }) }
})
