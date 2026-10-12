const { API_BASE_URL } = require('./config')

function request({ path, method = 'GET', data }) {
  const app = getApp()
  return new Promise((resolve, reject) => {
    app.whenIdentityReady().then(() => {
      const authorization = app.globalData.accessToken ? `Bearer ${app.globalData.accessToken}` : ''
      wx.request({
        url: `${API_BASE_URL}${path}`,
        method,
        data,
        header: {
          'content-type': 'application/json',
          ...(authorization ? { Authorization: authorization } : {}),
          'X-Demo-User': app.globalData.demoUser
        },
        success(response) {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            resolve(response.data)
          } else {
            reject(new Error(response.data.detail || '服务暂时不可用'))
          }
        },
        fail() { reject(new Error('网络连接失败，请稍后重试')) }
      })
    })
  })
}

function uploadScoreImage(filePath) {
  const app = getApp()
  return new Promise((resolve, reject) => {
    app.whenIdentityReady().then(() => {
      const authorization = app.globalData.accessToken ? `Bearer ${app.globalData.accessToken}` : ''
      let settled = false
      let uploadTask = null
      const finish = (callback, value) => {
        if (settled) return
        settled = true
        clearTimeout(timeout)
        callback(value)
      }
      const timeout = setTimeout(() => {
        finish(reject, new Error('图片识别等待时间较长，请稍后重试或改用手动录入'))
        if (uploadTask && typeof uploadTask.abort === 'function') uploadTask.abort()
      }, 45000)
      uploadTask = wx.uploadFile({
        url: `${API_BASE_URL}/score-imports`,
        filePath,
        name: 'image',
        header: {
          ...(authorization ? { Authorization: authorization } : {}),
          'X-Demo-User': app.globalData.demoUser
        },
        success(response) {
          let body = {}
          try { body = JSON.parse(response.data || '{}') } catch (_) { body = {} }
          if (response.statusCode >= 200 && response.statusCode < 300) finish(resolve, body)
          else finish(reject, new Error(body.detail || '上传失败，请稍后重试'))
        },
        fail(error) { finish(reject, new Error(error && error.errMsg ? '图片上传失败，请检查网络' : '图片上传失败，请稍后重试')) }
      })
    })
  })
}

module.exports = { request, uploadScoreImage }
