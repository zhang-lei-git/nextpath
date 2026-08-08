App({
  onLaunch() {
    let demoUser = wx.getStorageSync('nextpath_demo_user')
    if (!demoUser) {
      demoUser = `internal-${Date.now()}-${Math.random().toString(16).slice(2)}`
      wx.setStorageSync('nextpath_demo_user', demoUser)
    }
    this.globalData.demoUser = demoUser
    this.identityReady = new Promise((resolve) => this.login(resolve))
  },
  whenIdentityReady() {
    return this.identityReady || Promise.resolve()
  },
  login(done) {
    const finish = () => done && done()
    wx.login({
      success: ({ code }) => {
        if (!code) { finish(); return }
        wx.request({
          url: 'https://nextpath.top/api/v1/auth/wechat',
          method: 'POST',
          data: { code, legacy_owner_id: this.globalData.demoUser },
          success: (response) => {
            if (response.statusCode >= 200 && response.statusCode < 300 && response.data.access_token) {
              this.globalData.accessToken = response.data.access_token
              wx.setStorageSync('nextpath_access_token', response.data.access_token)
            } else {
              this.globalData.accessToken = ''
              wx.removeStorageSync('nextpath_access_token')
            }
            finish()
          },
          fail: finish
        })
      },
      fail: finish
    })
  },
  globalData: {
    demoUser: '',
    accessToken: wx.getStorageSync('nextpath_access_token') || ''
  }
})
