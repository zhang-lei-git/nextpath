const { API_BASE_URL } = require('./utils/config')
const PRIVACY_VERSION = '2026-10-20'

App({
  onLaunch() {
    this.globalData.accessToken = wx.getStorageSync('nextpath_access_token') || ''
    this.globalData.privacyAccepted = wx.getStorageSync('nextpath_privacy_version') === PRIVACY_VERSION
  },
  whenIdentityReady() {
    if (this.globalData.accessToken && this.globalData.privacyAccepted) return Promise.resolve()
    this.openLogin()
    return Promise.reject(new Error('请先同意隐私说明并完成微信登录'))
  },
  openLogin() {
    const pages = getCurrentPages()
    if (!pages.length || pages[pages.length - 1].route !== 'pages/login/index') wx.reLaunch({ url: '/pages/login/index' })
  },
  clearIdentity() {
    this.globalData.accessToken = ''
    this.globalData.privacyAccepted = false
    wx.removeStorageSync('nextpath_access_token')
    wx.removeStorageSync('nextpath_privacy_version')
  },
  async login() {
    if (this.loginPromise) return this.loginPromise
    this.loginPromise = this.performLogin()
    try { return await this.loginPromise } finally { this.loginPromise = null }
  },
  async performLogin() {
    if (typeof wx.requirePrivacyAuthorize === 'function') {
      await new Promise((resolve, reject) => wx.requirePrivacyAuthorize({
        success: resolve,
        fail: () => reject(new Error('请先同意微信隐私保护指引'))
      }))
    }
    const code = await new Promise((resolve, reject) => wx.login({
      timeout: 10000,
      success: (result) => result.code ? resolve(result.code) : reject(new Error('暂时无法获取微信登录凭证，请重试')),
      fail: () => reject(new Error('微信登录未完成，请重试'))
    }))
    const token = await new Promise((resolve, reject) => wx.request({
      url: `${API_BASE_URL}/auth/wechat`,
      method: 'POST', timeout: 15000,
      data: { code, guardian_consent: true, privacy_version: PRIVACY_VERSION },
      success: ({ statusCode, data }) => {
        if (statusCode >= 200 && statusCode < 300 && data && data.access_token) resolve(data.access_token)
        else reject(new Error(data && typeof data.detail === 'string' ? data.detail : '登录失败，请稍后重试'))
      },
      fail: () => reject(new Error('暂时无法连接，请检查网络后重试'))
    }))
    this.globalData.accessToken = token
    this.globalData.privacyAccepted = true
    wx.setStorageSync('nextpath_access_token', token)
    wx.setStorageSync('nextpath_privacy_version', PRIVACY_VERSION)
  },
  globalData: { accessToken: '', privacyAccepted: false }
})
