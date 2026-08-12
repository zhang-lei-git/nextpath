const { request, uploadScoreImage } = require('../../utils/request')

Page({
  data: {
    form: { name: '', exam_date: '', total_score: '', class_rank: '', grade_rank: '', grade_size: '', scores: { pe: '60' } },
    subjects: [],
    examFullMark: 640,
    hasSubjectScores: false,
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
    await this.loadScoringScheme()
    if (options.id) {
      try {
        const exam = await request({ path: `/exams/${options.id}` })
        const physical = exam.scores && exam.scores.pe !== undefined ? exam.scores.pe : (exam.physical_score === null || exam.physical_score === undefined ? 60 : exam.physical_score)
        const scores = { ...(exam.scores || {}), pe: String(physical) }
        const hasSubjectScores = Boolean(exam.score_includes_pe) && this.hasAcademicScores(scores)
        const total = exam.score_includes_pe ? exam.total_score : Number(exam.total_score) + Number(physical)
        this.setData({
          examId: exam.id,
          form: { ...exam, total_score: String(total), scores, class_rank: exam.class_rank || '', grade_rank: exam.grade_rank || '', grade_size: exam.grade_size || '' },
          examFullMark: this.data.examFullMark,
          hasSubjectScores
        })
        wx.setNavigationBarTitle({ title: '修改成绩' })
      } catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    }
  },
  updateField(event) {
    const key = event.currentTarget.dataset.key
    const value = event.detail.value
    this.setData({ [`form.${key}`]: value })
  },
  updateSubject(event) {
    const key = event.currentTarget.dataset.key
    const scores = { ...this.data.form.scores, [key]: event.detail.value }
    const hasSubjectScores = this.hasAcademicScores(scores)
    const total = hasSubjectScores ? this.subjectTotal(scores) : this.data.form.total_score
    this.setData({ 'form.scores': scores, 'form.total_score': total, hasSubjectScores })
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
          this.applyExtractedExam(extraction)
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
    if (scores.pe === undefined || scores.pe === '') scores.pe = '60'
    const hasSubjectScores = this.hasAcademicScores(scores)
    const total = hasSubjectScores ? this.subjectTotal(scores) : this.data.form.total_score
    const classRank = text.match(/班(?:级)?(?:第)?(\\d+)名/)
    const gradeRank = text.match(/年级(?:第)?(\\d+)名/)
    this.setData({
      voiceText: text,
      'form.scores': scores,
      'form.total_score': total,
      'form.class_rank': classRank ? classRank[1] : this.data.form.class_rank,
      'form.grade_rank': gradeRank ? gradeRank[1] : this.data.form.grade_rank,
      hasSubjectScores
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
      const hasSubjectScores = this.hasAcademicScores(form.scores)
      const totalScore = hasSubjectScores ? this.subjectTotal(form.scores) : Number(form.total_score)
      const physicalScore = Number(form.scores.pe === '' || form.scores.pe === undefined ? 60 : form.scores.pe)
      await request({
        path: this.data.examId ? `/exams/${this.data.examId}` : '/exams', method: this.data.examId ? 'PUT' : 'POST',
        data: {
          ...form,
          total_score: totalScore,
          total_full_mark: this.data.examFullMark,
          physical_score: physicalScore,
          score_includes_pe: true,
          class_rank: form.class_rank ? Number(form.class_rank) : null,
          grade_rank: form.grade_rank ? Number(form.grade_rank) : null,
          grade_size: form.grade_size ? Number(form.grade_size) : null,
          scores: hasSubjectScores
            ? Object.fromEntries(Object.entries(form.scores).filter(([, value]) => value !== '').map(([key, value]) => [key, Number(value)]))
            : {}
        }
      })
      wx.showToast({ title: this.data.examId ? '成绩已更新' : '成绩已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 500)
    } catch (error) { wx.showToast({ title: error.message, icon: 'none' }) }
    finally { this.setData({ saving: false }) }
  },
  hasAcademicScores(scores) {
    return Object.entries(scores).some(([key, value]) => key !== 'pe' && value !== '' && value !== undefined && value !== null)
  },
  subjectTotal(scores) {
    return Object.values(scores).reduce((sum, value) => sum + (Number(value) || 0), 0)
  },
  async loadScoringScheme() {
    try {
      const scheme = await request({ path: '/profile/scoring-scheme' })
      const labels = { chinese: '语文', math: '数学', english: '英语', physics: '物理', history: '历史', politics: '道法', chemistry: '化学', biology: '生物', geography: '地理', pe: '体育' }
      const scores = { ...this.data.form.scores }
      if (scores.pe === undefined) scores.pe = '60'
      this.setData({
        examFullMark: scheme.total_full_mark,
        subjects: Object.keys(scheme.counted_subjects).map((key) => ({ key, name: labels[key] || key, fullMark: scheme.counted_subjects[key] })),
        'form.scores': scores
      })
    } catch (_) { wx.showToast({ title: '暂时无法读取本届计分方案', icon: 'none' }) }
  },
  applyExtractedExam(extraction) {
    const scores = { ...(extraction.scores || {}) }
    scores.pe = scores.pe === undefined ? (extraction.physical_score === undefined || extraction.physical_score === null ? '60' : String(extraction.physical_score)) : String(scores.pe)
    const hasSubjectScores = this.hasAcademicScores(scores)
    const extractedTotal = Number(extraction.total_score)
    this.setData({
      form: {
        ...this.data.form,
        ...extraction,
        total_score: hasSubjectScores ? this.subjectTotal(scores) : (extractedTotal > 0 ? String(extractedTotal) : this.data.form.total_score),
        scores,
        class_rank: extraction.class_rank || '',
        grade_rank: extraction.grade_rank || '',
        grade_size: extraction.grade_size || ''
      },
      examFullMark: this.data.examFullMark,
      hasSubjectScores
    })
  }
})
