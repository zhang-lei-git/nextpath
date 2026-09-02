const { request } = require('../../utils/request')

Page({
  data: {
    exams: [],
    points: [],
    loading: true,
    activeTab: 'score',
    fullMark: 640,
    chartTitle: '总分变化',
    hasIncomplete: false
  },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true })
    try {
      const exams = await request({ path: '/exams' })
      let points = []
      try {
        const trend = await request({ path: '/exams/trend' })
        points = trend.points || []
      } catch (_) {
        points = []
      }
      this.setData({
        exams: exams.map((item) => ({
          ...item,
          score_rate: item.total_full_mark ? `${(item.total_score / item.total_full_mark * 100).toFixed(1)}%` : '—',
          grade_percentile: item.grade_rank && item.grade_size ? `年级前 ${(item.grade_rank / item.grade_size * 100).toFixed(1)}%` : '年级位置待补充'
        })),
        points,
        fullMark: points.length ? points[0].full_mark : 640,
        hasIncomplete: points.some((p) => !p.grade_percentile)
      })
      this.updateChartTitle()
    }
    catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  switchTab(event) {
    const tab = event.currentTarget.dataset.tab
    this.setData({ activeTab: tab })
    this.updateChartTitle()
  },
  updateChartTitle() {
    const titles = { score: '总分变化', rate: '得分率变化', percentile: '年级位置变化' }
    this.setData({ chartTitle: titles[this.data.activeTab] || '' })
  },
  add() { wx.navigateTo({ url: '/pages/score-entry/index' }) },
  edit(event) { wx.navigateTo({ url: `/pages/score-entry/index?id=${event.currentTarget.dataset.id}` }) },
  goHome() { wx.redirectTo({ url: '/pages/home/index' }) },
  showProfile() { wx.redirectTo({ url: '/pages/profile/index' }) }
})
