const { request, uploadScoreImage } = require('../../utils/request')

Page({
  data: {
    form: { name: '', exam_date: '', total_score: '', total_full_mark: '', class_rank: '', grade_rank: '', grade_size: '', scores: {} },
    subjects: [{ key: 'chinese', name: '语文' }, { key: 'math', name: '数学' }, { key: 'english', name: '英语' }, { key: 'physics', name: '物理' }, { key: 'history', name: '历史' }, { key: 'politics', name: '道法' }, { key: 'pe', name: '体育' }],
    uploading: false,
    saving: false,
    recording: false,
    voiceText: '',
    examId: ''
  },
  async onLoad(options) {
    const now = new Date()
    const date = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
    this.setData({ 'form.exam_date': date })
    if (options.id) {
      try {
        const exam = await request({ path: `/exams/${options.id}` })
        this.setData({ examId: exam.id, form: { ...exam, scores: exam.scores || {}, class_rank: exam.class_rank || '', grade_rank: exam.grade_rank || '', grade_size: exam.grade_size || '' } })
        wx.setNavigationBarTitle({ title: '修改成绩' })
      } catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    }
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
  voiceInput() {
    if (this.data.recording) {
      wx.stopRecord()
      return
    }
    wx.startRecord({
      timeout: 60000,
      success: (record) => {
        this.setData({ recording: false })
        wx.translateVoice({
          localId: record.tempFilePath,
          isShowProgressTips: 1,
          success: ({ translateResult }) => this.applyVoiceText(translateResult),
          fail: () => wx.showToast({ title: '语音转文字失败，请改用手动录入', icon: 'none' })
        })
      },
      fail: () => { this.setData({ recording: false }); wx.showToast({ title: '需要开启录音权限', icon: 'none' }) }
    })
    this.setData({ recording: true })
  },
  applyVoiceText(text) {
    const labels = { chinese: '语文', math: '数学', english: '英语', physics: '物理', history: '历史', politics: '(?:道法|政治)', pe: '体育' }
    const scores = { ...this.data.form.scores }
    Object.entries(labels).forEach(([key, label]) => {
      const matched = text.match(new RegExp(`${label}[为是：: ]*(\\d+(?:\\.\\d+)?)`))
      if (matched) scores[key] = matched[1]
    })
    const total = Object.values(scores).reduce((sum, value) => sum + (Number(value) || 0), 0)
    const classRank = text.match(/班(?:级)?(?:第)?(\\d+)名/)
    const gradeRank = text.match(/年级(?:第)?(\\d+)名/)
    this.setData({
      voiceText: text,
      'form.scores': scores,
      'form.total_score': total || this.data.form.total_score,
      'form.class_rank': classRank ? classRank[1] : this.data.form.class_rank,
      'form.grade_rank': gradeRank ? gradeRank[1] : this.data.form.grade_rank
    })
    wx.showToast({ title: '已填入待确认成绩', icon: 'none' })
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
        path: this.data.examId ? `/exams/${this.data.examId}` : '/exams', method: this.data.examId ? 'PUT' : 'POST',
        data: {
          ...form,
          total_score: Number(form.total_score),
          total_full_mark: form.total_full_mark ? Number(form.total_full_mark) : null,
          class_rank: form.class_rank ? Number(form.class_rank) : null,
          grade_rank: form.grade_rank ? Number(form.grade_rank) : null,
          grade_size: form.grade_size ? Number(form.grade_size) : null,
          scores: Object.fromEntries(Object.entries(form.scores).filter(([, value]) => value !== '').map(([key, value]) => [key, Number(value)]))
        }
      })
      wx.showToast({ title: this.data.examId ? '成绩已更新' : '成绩已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 500)
    } catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ saving: false }) }
  }
})
