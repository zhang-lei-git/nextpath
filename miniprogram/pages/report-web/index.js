const { request } = require('../../utils/request')

Page({
  data: { url: '', loading: true },
  async onLoad(options) {
    try {
      const access = await request({ path: `/reports/${options.id}/access`, method: 'POST' })
      this.setData({ url: access.url, loading: false })
    } catch (error) {
      this.setData({ loading: false })
      wx.showToast({ title: error.message, icon: 'none' })
    }
  }
})
