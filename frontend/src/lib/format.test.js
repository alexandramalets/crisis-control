import assert from 'node:assert/strict';
import test from 'node:test';
import { formatMoney, formatNumber, formatPercent } from './format.js';

test('пустое и нечисловое значение не превращается в ноль', () => {
  assert.equal(formatNumber(null), '—');
  assert.equal(formatNumber(undefined), '—');
  assert.equal(formatNumber(''), '—');
  assert.equal(formatNumber('нет'), '—');
  assert.equal(formatMoney(null), '—');
});

test('число форматируется по-русски', () => {
  assert.match(formatNumber(1200.5), /1[\s\u00a0]?200,5/);
  assert.match(formatPercent(-3.5), /3,5 %/);
  assert.match(formatPercent(3.5, { signed: true }), /^\+/);
});
