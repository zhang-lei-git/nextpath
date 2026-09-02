Component({
  properties: {
    points: { type: Array, value: [] },
    mode: { type: String, value: 'score' },
    fullMark: { type: Number, value: 0 }
  },
  observers: {
    'points, mode, fullMark'() { this.drawChart() }
  },
  lifetimes: {
    attached() { setTimeout(() => this.initCanvas(), 100) }
  },
  methods: {
    initCanvas() {
      const query = this.createSelectorQuery()
      query.select('#chart').fields({ node: true, size: true }).exec((res) => {
        if (!res[0]) return
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getWindowInfo().pixelRatio
        canvas.width = res[0].width * dpr
        canvas.height = res[0].height * dpr
        ctx.scale(dpr, dpr)
        this.canvas = canvas
        this.ctx = ctx
        this.width = res[0].width
        this.height = res[0].height
        this.drawChart()
      })
    },
    drawChart() {
      if (!this.ctx || !this.data.points.length) return
      const ctx = this.ctx
      const w = this.width
      const h = this.height
      const padding = { top: 30, right: 20, bottom: 40, left: 50 }
      const chartW = w - padding.left - padding.right
      const chartH = h - padding.top - padding.bottom
      ctx.clearRect(0, 0, w, h)

      const values = this.data.points.map((point) => this.getValue(point))
      const validValues = values.filter((value) => value !== null)
      if (!validValues.length) return
      let minVal
      let maxVal
      if (this.data.mode === 'score') {
        minVal = 0
        maxVal = this.data.fullMark || Math.max(...validValues) * 1.1
      } else if (this.data.mode === 'percentile') {
        minVal = 0
        maxVal = 100
      } else {
        minVal = Math.min(...validValues) * 0.9
        maxVal = Math.max(...validValues) * 1.1
        if (maxVal === minVal) maxVal = minVal + 10
      }
      const xStep = values.length > 1 ? chartW / (values.length - 1) : chartW / 2
      const range = maxVal - minVal || 1

      ctx.strokeStyle = '#E2E8F0'
      ctx.lineWidth = 0.5
      for (let index = 0; index <= 4; index += 1) {
        const y = padding.top + (chartH / 4) * index
        ctx.beginPath()
        ctx.moveTo(padding.left, y)
        ctx.lineTo(w - padding.right, y)
        ctx.stroke()
        const label = (maxVal - (range / 4) * index).toFixed(0)
        ctx.fillStyle = '#64748B'
        ctx.font = '10px -apple-system'
        ctx.textAlign = 'right'
        ctx.fillText(this.data.mode === 'percentile' ? `${label}%` : label, padding.left - 6, y + 3)
      }

      ctx.textAlign = 'center'
      ctx.fillStyle = '#64748B'
      ctx.font = '9px -apple-system'
      this.data.points.forEach((point, index) => {
        const x = values.length > 1 ? padding.left + index * xStep : padding.left + chartW / 2
        const dateText = point.exam_date || ''
        ctx.fillText(dateText.length >= 7 ? dateText.slice(5) : dateText, x, h - padding.bottom + 18)
      })

      ctx.strokeStyle = '#059669'
      ctx.lineWidth = 2
      ctx.lineJoin = 'round'
      ctx.beginPath()
      let started = false
      values.forEach((value, index) => {
        if (value === null) { started = false; return }
        const x = values.length > 1 ? padding.left + index * xStep : padding.left + chartW / 2
        const y = padding.top + chartH * (1 - (value - minVal) / range)
        if (!started) { ctx.moveTo(x, y); started = true } else ctx.lineTo(x, y)
      })
      ctx.stroke()
      values.forEach((value, index) => {
        if (value === null) return
        const x = values.length > 1 ? padding.left + index * xStep : padding.left + chartW / 2
        const y = padding.top + chartH * (1 - (value - minVal) / range)
        ctx.fillStyle = '#059669'
        ctx.beginPath()
        ctx.arc(x, y, 4, 0, Math.PI * 2)
        ctx.fill()
        ctx.fillStyle = '#FFFFFF'
        ctx.beginPath()
        ctx.arc(x, y, 2, 0, Math.PI * 2)
        ctx.fill()
      })
    },
    getValue(point) {
      if (this.data.mode === 'score') return point.total_score || null
      if (this.data.mode === 'rate') return point.score_rate || null
      if (this.data.mode === 'percentile') return point.grade_percentile || null
      return null
    }
  }
})
