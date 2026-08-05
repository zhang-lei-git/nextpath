const { request } = require('../../utils/request')

Page({
  data: { exams: [], loading: true },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true })
    try { this.setData({ exams: await request({ path: '/exams' }) }) }
    catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  add() { wx.navigateTo({ url: '/pages/score-entry/index' }) },
  edit(event) { wx.navigateTo({ url: `/pages/score-entry/index?id=${event.currentTarget.dataset.id}` }) }
})
