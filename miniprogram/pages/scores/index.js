const { request } = require('../../utils/request')

Page({
  data: { exams: [], loading: true },
  onShow() { this.load() },
  async load() {
    this.setData({ loading: true })
    try {
      const exams = await request({ path: '/exams' })
      this.setData({ exams: exams.map((item) => ({
        ...item,
        score_rate: item.total_full_mark ? `${(item.total_score / item.total_full_mark * 100).toFixed(1)}%` : '—',
        grade_percentile: item.grade_rank && item.grade_size ? `年级前 ${(item.grade_rank / item.grade_size * 100).toFixed(1)}%` : '年级位置待补充'
      })) })
    }
    catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ loading: false }) }
  },
  add() { wx.navigateTo({ url: '/pages/score-entry/index' }) },
  edit(event) { wx.navigateTo({ url: `/pages/score-entry/index?id=${event.currentTarget.dataset.id}` }) }
})
