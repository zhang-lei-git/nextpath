const ENV = 'production'

const API_BASE_URL = ENV === 'production'
  ? 'https://nextpath.top/api/v1'
  : 'http://127.0.0.1:8000/api/v1'

module.exports = { API_BASE_URL }
