const { request } = require('../../utils/request')

const fallback = {
  student_name: '小远',
  latest_exam: { name: '二模', exam_date: '2026-04-20', total_score: 615, class_rank: 28 },
  forecast: {
    tier: '省示范高中层',
    estimated_rank_range: [1200, 5000],
    target_gap: 5,
    confidence: 'low',
    basis: ['当前为演示基线估算，需继续补充考试与排名。'],
    model_version: 'baseline-2026.1', reference_year: 2026
  },
  action_items: [
    { title: '补齐排名信息', detail: '补录年级排名后，判断会更贴近孩子的真实位置。', priority: 'high' },
    { title: '关注大知识点失分', detail: '先看科目趋势，不进入繁重的错题分析。', priority: 'medium' }
  ],
  trend: [{ name: '一模', total_score: 603 }, { name: '二模', total_score: 615 }]
}

Page({
  data: { dashboard: fallback, loading: true, offline: false },
  onShow() { this.loadDashboard() },
  async loadDashboard() {
    this.setData({ loading: true })
    try {
      const dashboard = await request({ path: '/dashboard' })
      this.setData({ dashboard, offline: false })
    } catch (_) {
      this.setData({ dashboard: fallback, offline: true })
    } finally { this.setData({ loading: false }) }
  },
  goToEntry() {
    if (!this.data.dashboard.profile_complete) { wx.navigateTo({ url: '/pages/profile/index' }); return }
    wx.navigateTo({ url: '/pages/score-entry/index' })
  },
  goToAnalysis() { wx.navigateTo({ url: '/pages/analysis/index' }) },
  showProfile() { wx.navigateTo({ url: '/pages/profile/index' }) }
})
