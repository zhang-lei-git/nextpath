const { request, uploadScoreImage } = require('../../utils/request')

Page({
  data: {
    form: { name: '', exam_date: '', total_score: '', class_rank: '', grade_rank: '', scores: {} },
    subjects: [{ key: 'chinese', name: '语文' }, { key: 'math', name: '数学' }, { key: 'english', name: '英语' }, { key: 'physics', name: '物理' }, { key: 'history', name: '历史' }, { key: 'politics', name: '道法' }, { key: 'pe', name: '体育' }],
    uploading: false,
    saving: false
  },
  onLoad() {
    const now = new Date()
    const date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    this.setData({ 'form.exam_date': date })
  },
  updateField(event) {
    const key = event.currentTarget.dataset.key
    this.setData({ [`form.${key}`]: event.detail.value })
  },
  updateSubject(event) {
    const key = event.currentTarget.dataset.key
    const scores = { ...this.data.form.scores, [key]: event.detail.value }
    const total = Object.values(scores).reduce((sum, value) => sum + (Number(value) || 0), 0)
    this.setData({ 'form.scores': scores, 'form.total_score': total || '' })
  },
  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: async ({ tempFiles }) => {
        this.setData({ uploading: true })
        try {
          const result = await uploadScoreImage(tempFiles[0].tempFilePath)
          const extraction = result.extraction
          this.setData({ form: { ...this.data.form, ...extraction, scores: extraction.scores || {} } })
          wx.showToast({ title: '已生成待确认记录', icon: 'none' })
        } catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
        finally { this.setData({ uploading: false }) }
      }
    })
  },
  async submit() {
    const form = this.data.form
    if (!form.name || !form.exam_date || form.total_score === '') {
      wx.showToast({ title: '请填写考试名称、日期和总分', icon: 'none' })
      return
    }
    this.setData({ saving: true })
    try {
      await request({
        path: '/exams', method: 'POST',
        data: {
          ...form,
          total_score: Number(form.total_score),
          class_rank: form.class_rank ? Number(form.class_rank) : null,
          grade_rank: form.grade_rank ? Number(form.grade_rank) : null,
          scores: Object.fromEntries(Object.entries(form.scores).filter(([, value]) => value !== '').map(([key, value]) => [key, Number(value)]))
        }
      })
      wx.showToast({ title: '成绩已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 500)
    } catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ saving: false }) }
  }
})
