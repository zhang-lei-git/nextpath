const { API_BASE_URL } = require('../../utils/config')

Page({
  data: { url: '' },
  onLoad(options) {
    this.setData({ url: `${API_BASE_URL}/reports/published/${options.id}` })
  }
})
