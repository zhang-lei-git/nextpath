const { request } = require('../../utils/request')

Page({
  data: {
    dashboard: null, home: null, firstScreen: null,
    loading: true, loadError: false
  },
  onShow() { this.loadDashboard() },
  async loadDashboard() {
    this.setData({ loading: true })
    try {
      const dashboard = await request({ path: '/dashboard' })
      const firstScreen = dashboard.first_screen || null
      this.setData({ dashboard, firstScreen, loadError: false })
      this.setData({ home: this.buildHomeView(dashboard) })
    } catch (_) {
      this.setData({ dashboard: null, home: null, firstScreen: null, loadError: true })
    } finally { this.setData({ loading: false }) }
  },
  buildHomeView(dashboard) {
    const forecast = dashboard.forecast
    if (!forecast) return null
    const current = forecast.current_snapshot || null
    const projection = (forecast.exam_outcomes || []).find((item) => item.key === 'steady') || forecast.reasonable_projection || null
    const schoolGroups = (tiers) => {
      const labels = { reach: '可冲刺', match: '较匹配', safe: '相对稳妥' }
      return ['reach', 'match', 'safe'].map((key) => ({
        key,
        label: labels[key],
        schools: (tiers && tiers[key] || []).slice(0, 2)
      })).filter((group) => group.schools.length)
    }
    return {
      hasTarget: Boolean(dashboard.target_school),
      targetCurrent: forecast.target_comparison && forecast.target_comparison.current_relation,
      targetRelation: forecast.target_comparison && forecast.target_comparison.projected_relation,
      positionLabel: dashboard.latest_exam && dashboard.latest_exam.grade_rank && dashboard.latest_exam.grade_size
        ? `年级第 ${dashboard.latest_exam.grade_rank} / ${dashboard.latest_exam.grade_size} 名`
        : dashboard.latest_exam && dashboard.latest_exam.class_rank
          ? `班级第 ${dashboard.latest_exam.class_rank} 名`
          : '排名信息待补充',
      current,
      projection,
      currentSchoolGroups: schoolGroups(current && current.school_tiers),
      projectionSchoolGroups: schoolGroups(projection && projection.school_tiers),
      projectionRange: projection && projection.total_range && `${projection.total_range[0]}–${projection.total_range[1]}`,
      projectionRank: projection && projection.estimated_rank_range && projection.estimated_rank_range[0] > 0
        ? `全区第 ${projection.estimated_rank_range[0].toLocaleString()}–${projection.estimated_rank_range[1].toLocaleString()} 名`
        : '位次仍需补充信息后估算'
    }
  },
  retry() { this.loadDashboard() },
  goToEntry() {
    if (!this.data.dashboard.profile_complete) { wx.navigateTo({ url: '/pages/profile/index' }); return }
    wx.navigateTo({ url: '/pages/score-entry/index' })
  },
  goToAnalysis() { wx.navigateTo({ url: '/pages/analysis/index' }) },
  openSchool(event) { wx.navigateTo({ url: `/pages/school-detail/index?name=${encodeURIComponent(event.currentTarget.dataset.name)}` }) },
  goToScores() { wx.navigateTo({ url: '/pages/scores/index' }) },
  goToTrend() { wx.navigateTo({ url: '/pages/scores/index' }) },
  goToReports() { wx.navigateTo({ url: '/pages/reports/index' }) },
  goSchool(event) { wx.navigateTo({ url: `/pages/school-detail/index?name=${encodeURIComponent(event.currentTarget.dataset.name)}` }) },
  showProfile() { wx.navigateTo({ url: '/pages/profile/index' }) },
  completeLatestExam() {
    const latest = this.data.dashboard && this.data.dashboard.latest_exam
    if (latest) wx.navigateTo({ url: `/pages/score-entry/index?id=${latest.id}` })
  }
})
