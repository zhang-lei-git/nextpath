const { API_BASE_URL } = require('./config')

function request({ path, method = 'GET', data }) {
  const app = getApp()
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${API_BASE_URL}${path}`,
      method,
      data,
      header: {
        'content-type': 'application/json',
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
}

function uploadScoreImage(filePath) {
  const app = getApp()
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${API_BASE_URL}/score-imports`,
      filePath,
      name: 'image',
      header: { 'X-Demo-User': app.globalData.demoUser },
      success(response) {
        const body = JSON.parse(response.data)
        if (response.statusCode >= 200 && response.statusCode < 300) resolve(body)
        else reject(new Error(body.detail || '上传失败'))
      },
      fail() { reject(new Error('图片上传失败，请检查网络')) }
    })
  })
}

module.exports = { request, uploadScoreImage }
