#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

function verifyReport(filePath) {
  const errors=[];
  const warnings=[];
  const html=fs.readFileSync(filePath,'utf8');

  if (/\{\{[A-Z0-9_]+\}\}/.test(html)) errors.push('unresolved template placeholder found');
  for (const required of ['glance','conclusion','data','subjects','school','path','action','decisions','sources','scoreChart','rankChart']) {
    if (!html.includes(`id="${required}"`)) errors.push(`missing required id: ${required}`);
  }
  const ids=[...html.matchAll(/\sid="([^"]+)"/g)].map(match=>match[1]);
  const duplicates=[...new Set(ids.filter((id,index)=>ids.indexOf(id)!==index))];
  if (duplicates.length) errors.push(`duplicate ids: ${duplicates.join(', ')}`);

  const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match=>match[1]);
  for (const [index,script] of scripts.entries()) {
    try { new Function(script); }
    catch (error) { errors.push(`script ${index+1} syntax error: ${error.message}`); }
  }

  if (!/\.sec-num\{[^}]*min-width:86px/s.test(html)) warnings.push('section number width guard not found');
  if (!/\.entrance-marker\.school\{[^}]*top:94px/s.test(html)) warnings.push('entrance marker vertical separation guard not found');
  if (Buffer.byteLength(html)>500000) warnings.push('report exceeds 500 KB');

  let previewPath=null;
  const qlmanage=spawnSync('which',['qlmanage'],{encoding:'utf8'});
  if (qlmanage.status===0) {
    const previewDir=fs.mkdtempSync(path.join(os.tmpdir(),'student-report-preview-'));
    const preview=spawnSync('qlmanage',['-t','-s','1400','-o',previewDir,path.resolve(filePath)],{encoding:'utf8'});
    if (preview.status!==0) warnings.push(`Quick Look preview failed: ${preview.stderr.trim()}`);
    else {
      const png=fs.readdirSync(previewDir).find(name=>name.endsWith('.png'));
      if (png) previewPath=path.join(previewDir,png);
      else warnings.push('Quick Look produced no PNG preview');
    }
  }

  return {errors,warnings,previewPath};
}

if (require.main===module) {
  const filePath=process.argv[2];
  if (!filePath) {
    console.error('Usage: node verify-report.js <report.html>');
    process.exit(2);
  }
  try {
    const result=verifyReport(filePath);
    for(const warning of result.warnings) console.warn(`WARNING: ${warning}`);
    for(const error of result.errors) console.error(`ERROR: ${error}`);
    if(result.previewPath) console.log(`Preview: ${result.previewPath}`);
    if(result.errors.length) process.exit(1);
    console.log('Report verification passed.');
  } catch(error) {
    console.error(error.message);
    process.exit(1);
  }
}

module.exports={verifyReport};
