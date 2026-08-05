const PRODUCTION_API_BASE_URL = 'https://nextpath.top/api/v1'
const DEVTOOLS_API_BASE_URL = 'https://120.26.231.225/api/v1'

function isDevtools() {
  try {
    return wx.getSystemInfoSync().platform === 'devtools'
  } catch (_) {
    return false
  }
}

// Keep desktop development on the deployed ECS while the production domain is under review.
const API_BASE_URL = isDevtools() ? DEVTOOLS_API_BASE_URL : PRODUCTION_API_BASE_URL

module.exports = { API_BASE_URL }
