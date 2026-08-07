const { request } = require('../../utils/request')

Page({
  data: {
    form: { student_name: '', junior_school: '', grade: '初三', class_type_raw: '', class_type_standard: '未知', target_school: '' },
    grades: ['初一', '初二', '初三'], gradeIndex: 2, saving: false,
    classTypes: ['未知', '创新', '重点', '平行'], classTypeIndex: 0,
    juniorMatches: [], targetMatches: []
  },
  async onLoad() {
    try {
      const profile = await request({ path: '/profile' })
      const form = {
        student_name: profile.student_name || '',
        junior_school: profile.junior_school || '',
        grade: profile.grade || '初三',
        class_type_raw: profile.class_type_raw || '',
        class_type_standard: profile.class_type_standard || '未知',
        target_school: profile.target_school || ''
      }
      this.setData({
        form,
        gradeIndex: this.data.grades.indexOf(form.grade),
        classTypeIndex: Math.max(0, this.data.classTypes.indexOf(form.class_type_standard))
      })
    } catch (_) { wx.showToast({ title: '暂时无法读取档案', icon: 'none' }) }
  },
  input(event) {
    const key = event.currentTarget.dataset.key
    const value = event.detail.value
    this.setData({ [`form.${key}`]: value })
    if (key === 'junior_school') this.searchSchool(value, 'junior', 'juniorMatches')
    if (key === 'target_school') this.searchSchool(value, 'senior', 'targetMatches')
  },
  searchSchool(query, schoolStage, resultKey) {
    clearTimeout(this.searchTimer)
    if (query.trim().length < 2) {
      this.setData({ [resultKey]: [] })
      return
    }
    this.searchTimer = setTimeout(async () => {
      try {
        const result = await request({
          path: '/data/consumer/school-search',
          data: { region: '西安', reference_year: 2026, query: query.trim(), school_stage: schoolStage }
        })
        if (this.data.form[schoolStage === 'junior' ? 'junior_school' : 'target_school'] === query) {
          this.setData({ [resultKey]: result.facts || [] })
        }
      } catch (_) { this.setData({ [resultKey]: [] }) }
    }, 250)
  },
  selectSchool(event) {
    const key = event.currentTarget.dataset.key
    this.setData({ [`form.${key}`]: event.currentTarget.dataset.name, [key === 'junior_school' ? 'juniorMatches' : 'targetMatches']: [] })
  },
  gradeChange(event) {
    const gradeIndex = Number(event.detail.value)
    this.setData({ 'form.grade': this.data.grades[gradeIndex], gradeIndex })
  },
  classTypeChange(event) {
    const classTypeIndex = Number(event.detail.value)
    this.setData({ 'form.class_type_standard': this.data.classTypes[classTypeIndex], classTypeIndex })
  },
  async save() {
    const form = this.data.form
    if (!form.student_name.trim() || !form.junior_school.trim()) {
      wx.showToast({ title: '请填写孩子称呼和所在初中', icon: 'none' }); return
    }
    this.setData({ saving: true })
    try {
      await request({ path: '/profile', method: 'PUT', data: form })
      wx.showToast({ title: '档案已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 400)
    } catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ saving: false }) }
  }
})
