Page({
  continue() {
    if (typeof wx.requirePrivacyAuthorize !== 'function') {
      getApp().startIdentity()
      wx.navigateBack()
      return
    }
    wx.requirePrivacyAuthorize({
      success: () => { getApp().startIdentity(); wx.navigateBack() },
      fail: () => wx.showToast({ title: '请先同意隐私保护指引', icon: 'none' })
    })
  }
})
