App({
  onLaunch() {
    let demoUser = wx.getStorageSync('nextpath_demo_user')
    if (!demoUser) {
      demoUser = `internal-${Date.now()}-${Math.random().toString(16).slice(2)}`
      wx.setStorageSync('nextpath_demo_user', demoUser)
    }
    this.globalData.demoUser = demoUser
  },
  globalData: { demoUser: '' }
})
