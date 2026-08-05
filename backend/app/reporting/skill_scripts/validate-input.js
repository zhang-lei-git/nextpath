#!/usr/bin/env node
'use strict';

const fs = require('fs');

const SOURCE_LEVELS = new Set(['official', 'media', 'third_party', 'missing']);
const ALLOWED_HTML_TAGS = new Set(['b', 'strong', 'em', 'span', 'br']);

function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function validateInlineHtml(value, path, errors) {
  if (typeof value !== 'string') return;
  const tags = [...value.matchAll(/<\/?([a-zA-Z0-9]+)(?:\s[^>]*)?>/g)].map(match => match[1].toLowerCase());
  for (const tag of tags) {
    if (!ALLOWED_HTML_TAGS.has(tag)) errors.push(`${path}: unsupported HTML tag <${tag}>`);
  }
  if (/\son\w+\s*=|javascript:/i.test(value)) errors.push(`${path}: event handlers and javascript URLs are not allowed`);
}

function walkHtmlFields(value, path, errors) {
  if (!value || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value)) {
    const childPath = path ? `${path}.${key}` : key;
    if (key.endsWith('Html')) validateInlineHtml(child, childPath, errors);
    if (child && typeof child === 'object') walkHtmlFields(child, childPath, errors);
  }
}

function validateInput(data) {
  const errors = [];
  const warnings = [];

  for (const key of ['meta', 'glance', 'subjects', 'data', 'conclusion', 'school', 'path', 'action', 'decisions', 'sources']) {
    if (data[key] === undefined) errors.push(`missing top-level field: ${key}`);
  }
  if (errors.length) return { errors, warnings };

  if (!Array.isArray(data.subjects) || data.subjects.length < 3) errors.push('subjects must contain at least three subjects');
  if (!Array.isArray(data.data.exams) || data.data.exams.length < 1) errors.push('data.exams must contain at least one exam');
  if (!isNumber(data.data.classSize) || data.data.classSize <= 0) errors.push('data.classSize must be a positive number');

  const subjectMap = new Map();
  for (const [index, subject] of (data.subjects || []).entries()) {
    const path = `subjects[${index}]`;
    if (!subject.key || !subject.name) errors.push(`${path}: key and name are required`);
    if (subjectMap.has(subject.key)) errors.push(`${path}: duplicate subject key ${subject.key}`);
    subjectMap.set(subject.key, subject);
    if (!isNumber(subject.max) || subject.max <= 0) errors.push(`${path}.max must be a positive number`);
    if (!isNumber(subject.finalScore) || subject.finalScore < 0) errors.push(`${path}.finalScore must be a non-negative number`);
    if (isNumber(subject.finalScore) && isNumber(subject.max) && subject.finalScore > subject.max) {
      errors.push(`${path}: final score ${subject.finalScore} exceeds full mark ${subject.max}`);
    }
  }

  let finalSum = 0;
  for (const subject of data.subjects || []) {
    if (subject.countInTotal !== false && isNumber(subject.finalScore)) finalSum += subject.finalScore;
  }
  if (isNumber(data.meta.reportedTotal)) {
    const tolerance = data.validation?.totalTolerance ?? 0.01;
    const difference = Math.abs(finalSum - data.meta.reportedTotal);
    if (difference > tolerance) {
      const message = `reported total ${data.meta.reportedTotal} does not equal subject sum ${Number(finalSum.toFixed(2))}`;
      if (data.validation?.allowTotalMismatch) warnings.push(message);
      else errors.push(message);
    }
  }

  for (const [index, exam] of (data.data.exams || []).entries()) {
    const path = `data.exams[${index}]`;
    if (!exam.label || !exam.display) errors.push(`${path}: label and display are required`);
    if (!exam.scores || typeof exam.scores !== 'object') {
      errors.push(`${path}.scores must be an object`);
      continue;
    }
    for (const [key, score] of Object.entries(exam.scores)) {
      const subject = subjectMap.get(key);
      if (!subject) {
        warnings.push(`${path}.scores.${key}: no matching subject definition`);
        continue;
      }
      if (!isNumber(score) || score < 0) errors.push(`${path}.scores.${key} must be a non-negative number`);
      else if (score > subject.max) errors.push(`${path}.scores.${key}: score ${score} exceeds full mark ${subject.max}`);
    }
    if (exam.rank !== undefined && exam.rank !== null) {
      if (!isNumber(exam.rank) || exam.rank < 1 || exam.rank > data.data.classSize) {
        errors.push(`${path}.rank must be between 1 and classSize (${data.data.classSize})`);
      }
    }
  }

  for (const [index, evidence] of (data.school.evidence || []).entries()) {
    const path = `school.evidence[${index}]`;
    if (!SOURCE_LEVELS.has(evidence.level)) errors.push(`${path}.level must be official, media, third_party, or missing`);
    if (evidence.level !== 'missing' && !evidence.detail) warnings.push(`${path}: evidence detail is empty`);
    const combined = `${evidence.metric || ''} ${evidence.title || ''} ${evidence.detail || ''}`;
    if (/985|211/.test(combined) && /\d+(?:\.\d+)?\s*%/.test(combined) && !evidence.url) {
      errors.push(`${path}: exact 985/211 percentage requires a source URL`);
    }
  }

  const exactProbabilityText = JSON.stringify(data).match(/(?:985|211)[^。；,，]{0,24}(?:概率|率)[^。；,，]{0,12}\d+(?:\.\d+)?\s*%/g) || [];
  for (const claim of exactProbabilityText) warnings.push(`review exact admission probability claim: ${claim}`);

  walkHtmlFields(data, '', errors);
  return { errors, warnings, computed: { finalSubjectSum: Number(finalSum.toFixed(2)) } };
}

function loadJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'));
}

if (require.main === module) {
  const filePath = process.argv[2];
  if (!filePath) {
    console.error('Usage: node validate-input.js <input.json>');
    process.exit(2);
  }
  let result;
  try {
    result = validateInput(loadJson(filePath));
  } catch (error) {
    console.error(`Invalid JSON: ${error.message}`);
    process.exit(2);
  }
  for (const warning of result.warnings) console.warn(`WARNING: ${warning}`);
  for (const error of result.errors) console.error(`ERROR: ${error}`);
  if (result.computed) console.log(`Computed subject sum: ${result.computed.finalSubjectSum}`);
  if (result.errors.length) process.exit(1);
  console.log('Validation passed.');
}

module.exports = { validateInput, loadJson };
