const { request } = require('../../utils/request')

Page({
  data: { form: { student_name: '', junior_school: '', grade: '初三', target_school: '' }, grades: ['初一', '初二', '初三'], gradeIndex: 2, saving: false },
  async onLoad() {
    try {
      const profile = await request({ path: '/profile' })
      const form = {
        student_name: profile.student_name || '',
        junior_school: profile.junior_school || '',
        grade: profile.grade || '初三',
        target_school: profile.target_school || ''
      }
      this.setData({ form, gradeIndex: this.data.grades.indexOf(form.grade) })
    } catch (_) { wx.showToast({ title: '暂时无法读取档案', icon: 'none' }) }
  },
  input(event) { this.setData({ [`form.${event.currentTarget.dataset.key}`]: event.detail.value }) },
  gradeChange(event) {
    const gradeIndex = Number(event.detail.value)
    this.setData({ 'form.grade': this.data.grades[gradeIndex], gradeIndex })
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
