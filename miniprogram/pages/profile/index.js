const { request } = require('../../utils/request')

Page({
  data: { form: { student_name: '', junior_school: '', grade: '初三', target_school: '' }, grades: ['初一', '初二', '初三'], saving: false },
  async onLoad() {
    try {
      const profile = await request({ path: '/profile' })
      this.setData({ form: { ...this.data.form, ...profile } })
    } catch (_) { wx.showToast({ title: '暂时无法读取档案', icon: 'none' }) }
  },
  input(event) { this.setData({ [`form.${event.currentTarget.dataset.key}`]: event.detail.value }) },
  gradeChange(event) { this.setData({ 'form.grade': this.data.grades[event.detail.value] }) },
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
