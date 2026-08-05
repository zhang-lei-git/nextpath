(() => {
  const report = window.__STUDENT_REPORT_DATA__;
  if (!report || !report.data || !Array.isArray(report.data.exams)) return;

  const NS = 'http://www.w3.org/2000/svg';
  const palette = ['#2b6f9f', '#1f8a7a', '#2e8b57', '#c0503f', '#c9872f', '#7456a5'];
  const neutral = { grid:'#e2e8ee', text:'#5f6b78', faint:'#8a95a1', ink:'#1b2733', highlight:'#c9872f' };
  const subjects = (report.subjects || []).filter(subject => subject.trend);
  const exams = report.data.exams.filter(exam => exam.comparable !== false);
  const subjectColors = Object.fromEntries(subjects.map((subject, index) => [subject.key, subject.seriesColor || palette[index % palette.length]]));

  function el(name, attrs = {}, text = '') {
    const node = document.createElementNS(NS, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    if (text !== '') node.textContent = text;
    return node;
  }

  function linePath(points) {
    return points.map((point, index) => `${index ? 'L' : 'M'} ${point[0].toFixed(1)} ${point[1].toFixed(1)}`).join(' ');
  }

  function drawLegend() {
    const legend = document.getElementById('scoreLegend');
    if (!legend) return;
    legend.innerHTML = '';
    for (const subject of subjects) {
      const item = document.createElement('span');
      item.className = 'legend-item';
      item.innerHTML = `<i class="swatch" style="background:${subjectColors[subject.key]}"></i>${subject.name}`;
      legend.appendChild(item);
    }
  }

  function drawScoreChart() {
    const svg = document.getElementById('scoreChart');
    if (!svg || subjects.length === 0 || exams.length < 2) return;
    svg.innerHTML = '';
    const W=980, H=400, m={l:52,r:86,t:30,b:72};
    const plotW=W-m.l-m.r, plotH=H-m.t-m.b;
    const allRates=[];
    for (const subject of subjects) {
      for (const exam of exams) {
        const score=exam.scores?.[subject.key];
        if (typeof score === 'number') allRates.push(score/subject.max*100);
      }
    }
    const observedMin = allRates.length ? Math.min(...allRates) : 60;
    const yMin = Math.max(0, Math.min(70, Math.floor((observedMin-5)/10)*10));
    const yMax = 100;
    const x = index => m.l + plotW*index/(exams.length-1);
    const y = value => m.t + plotH*(yMax-value)/(yMax-yMin);

    if (yMin < 90) {
      svg.appendChild(el('rect',{x:m.l,y:y(100),width:plotW,height:y(90)-y(100),fill:'#f0f7f2'}));
      svg.appendChild(el('text',{x:W-m.r+6,y:y(95)+4,fill:'#9fb8a9','font-size':11},'90%+'));
    }
    for (let tick=yMin; tick<=100; tick+=10) {
      svg.appendChild(el('line',{x1:m.l,y1:y(tick),x2:W-m.r,y2:y(tick),stroke:neutral.grid,'stroke-width':1}));
      svg.appendChild(el('text',{x:m.l-10,y:y(tick)+4,'text-anchor':'end',fill:neutral.text,'font-size':12},`${tick}%`));
    }
    exams.forEach((exam,index) => {
      svg.appendChild(el('text',{x:x(index),y:H-40,'text-anchor':'end',fill:index===exams.length-1?neutral.highlight:neutral.text,
        'font-size':index===exams.length-1?12:11,'font-weight':index===exams.length-1?800:400,
        transform:`rotate(-32 ${x(index)} ${H-40})`},exam.label));
    });
    if (exams.length > 2) {
      const divider=(x(exams.length-2)+x(exams.length-1))/2;
      svg.appendChild(el('line',{x1:divider,y1:m.t-6,x2:divider,y2:H-m.b,stroke:neutral.highlight,'stroke-width':1.5,'stroke-dasharray':'5 5',opacity:.85}));
    }

    subjects.forEach(subject => {
      const values=exams.map((exam,index) => {
        const score=exam.scores?.[subject.key];
        return typeof score === 'number' ? {index,rate:score/subject.max*100} : null;
      }).filter(Boolean);
      if (values.length < 2) return;
      const points=values.map(value => [x(value.index),y(value.rate)]);
      const color=subjectColors[subject.key];
      svg.appendChild(el('path',{d:linePath(points),fill:'none',stroke:color,'stroke-width':3,'stroke-linejoin':'round','stroke-linecap':'round',opacity:.92}));
      points.forEach((point,index) => svg.appendChild(el('circle',{cx:point[0],cy:point[1],r:index===points.length-1?5.5:3.4,
        fill:index===points.length-1?'#fff':color,stroke:color,'stroke-width':index===points.length-1?3:1.2})));
      const last=points[points.length-1];
      const lastRate=values[values.length-1].rate;
      svg.appendChild(el('text',{x:W-m.r+8,y:last[1]+4,fill:color,'font-size':12.5,'font-weight':800},`${subject.name} ${lastRate.toFixed(1)}`));
    });
    svg.appendChild(el('rect',{x:m.l,y:m.t,width:plotW,height:plotH,fill:'none',stroke:neutral.grid,'stroke-width':1}));
  }

  function drawRankChart() {
    const svg=document.getElementById('rankChart');
    const ranked=exams.filter(exam => typeof exam.rank === 'number');
    if (!svg || ranked.length < 2) return;
    svg.innerHTML='';
    const W=560,H=380,m={l:46,r:26,t:34,b:70};
    const plotW=W-m.l-m.r,plotH=H-m.t-m.b;
    const classSize=report.data.classSize;
    const minRank=Math.max(1,Math.floor(Math.min(...ranked.map(exam=>exam.rank))-5));
    const maxRank=Math.min(classSize,Math.ceil(Math.max(...ranked.map(exam=>exam.rank))+6));
    const x=index=>m.l+plotW*index/(ranked.length-1);
    const y=value=>m.t+plotH*(value-minRank)/(maxRank-minRank || 1);
    const target=Math.max(minRank,Math.round(classSize/2));
    svg.appendChild(el('rect',{x:m.l,y:m.t,width:plotW,height:Math.max(0,y(target)-m.t),fill:'#eef6f0'}));
    svg.appendChild(el('text',{x:m.l+6,y:m.t+16,fill:'#7fa88d','font-size':11.5,'font-weight':700},`前 ${target} 名`));
    const ticks=5;
    for(let i=0;i<ticks;i++){
      const tick=Math.round(minRank+(maxRank-minRank)*i/(ticks-1));
      svg.appendChild(el('line',{x1:m.l,y1:y(tick),x2:W-m.r,y2:y(tick),stroke:neutral.grid,'stroke-width':1}));
      svg.appendChild(el('text',{x:m.l-10,y:y(tick)+4,'text-anchor':'end',fill:neutral.text,'font-size':12},`${tick}`));
    }
    ranked.forEach((exam,index)=>svg.appendChild(el('text',{x:x(index),y:H-36,'text-anchor':'end',fill:neutral.text,'font-size':10.5,
      transform:`rotate(-32 ${x(index)} ${H-36})`},exam.label)));
    const points=ranked.map((exam,index)=>[x(index),y(exam.rank)]);
    svg.appendChild(el('path',{d:linePath(points)+` L ${x(ranked.length-1)} ${y(maxRank)} L ${x(0)} ${y(maxRank)} Z`,fill:'#2b6f9f',opacity:.08}));
    svg.appendChild(el('path',{d:linePath(points),fill:'none',stroke:'#2b6f9f','stroke-width':3,'stroke-linejoin':'round','stroke-linecap':'round'}));
    const best=Math.min(...ranked.map(exam=>exam.rank));
    const worst=Math.max(...ranked.map(exam=>exam.rank));
    points.forEach((point,index)=>{
      const rank=ranked[index].rank;
      const color=rank===best?'#2e8b57':rank===worst?'#c0503f':'#2b6f9f';
      svg.appendChild(el('circle',{cx:point[0],cy:point[1],r:rank===best||rank===worst?6:4.5,fill:'#fff',stroke:color,'stroke-width':3}));
      svg.appendChild(el('text',{x:point[0],y:point[1]-11,'text-anchor':'middle',fill:color,'font-size':11.5,'font-weight':800},`${rank}`));
    });
    const average=ranked.reduce((sum,exam)=>sum+exam.rank,0)/ranked.length;
    svg.appendChild(el('line',{x1:m.l,y1:y(average),x2:W-m.r,y2:y(average),stroke:neutral.highlight,'stroke-width':1.5,'stroke-dasharray':'5 5'}));
    svg.appendChild(el('text',{x:W-m.r,y:y(average)-7,'text-anchor':'end',fill:neutral.highlight,'font-size':11.5,'font-weight':700},`平均 ${average.toFixed(1)} 名`));
    svg.appendChild(el('rect',{x:m.l,y:m.t,width:plotW,height:plotH,fill:'none',stroke:neutral.grid,'stroke-width':1}));
  }

  drawLegend();
  drawScoreChart();
  drawRankChart();
})();
