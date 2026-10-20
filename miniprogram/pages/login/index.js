Page({
  data: { agreed: false, loggingIn: false, checking: false, error: '' },
  async onShow() {
    const app = getApp()
    if (!app.globalData.accessToken || !app.globalData.privacyAccepted) return
    this.setData({ checking: true })
    try {
      const { request } = require('../../utils/request')
      await request({ path: '/profile' })
      wx.reLaunch({ url: '/pages/home/index' })
    } catch (_) { app.clearIdentity() }
    finally { this.setData({ checking: false }) }
  },
  agree(event) { this.setData({ agreed: event.detail.value.includes('agree'), error: '' }) },
  showPrivacy() { wx.navigateTo({ url: '/pages/privacy/index' }) },
  async login() {
    if (this.data.loggingIn || this.data.checking) return
    if (!this.data.agreed) { this.setData({ error: '请先阅读隐私说明并确认监护人授权' }); return }
    this.setData({ loggingIn: true, error: '' })
    try {
      await getApp().login()
      wx.reLaunch({ url: '/pages/home/index' })
    } catch (error) { this.setData({ error: error.message }) }
    finally { this.setData({ loggingIn: false }) }
  }
})
