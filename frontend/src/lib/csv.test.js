import assert from 'node:assert/strict';
import test from 'node:test';
import { toCsv } from './csv.js';

test('отчёт экранирует разделитель и кавычки', () => {
  const csv = toCsv(
    [{ key: 'name', title: 'Показатель' }, { key: 'value', title: 'Значение' }],
    [{ name: 'Выручка; план', value: 'текст "внутри"' }],
  );
  assert.ok(csv.startsWith('\uFEFF'));
  assert.match(csv, /"Выручка; план"/);
  assert.match(csv, /"текст ""внутри"""/);
});

test('формула Excel не остаётся исполняемой, отрицательное число остаётся числом', () => {
  const csv = toCsv(
    [{ key: 'name', title: 'Имя' }, { key: 'value', title: 'Значение' }],
    [{ name: '=1+1', value: -12.5 }],
  );
  assert.match(csv, /'=1\+1/);
  assert.match(csv, /-12[,.]5/);
  assert.doesNotMatch(csv, /^-12/m);
});

test('пустые наблюдения выгружаются пустой ячейкой', () => {
  const csv = toCsv([{ key: 'value', title: 'Факт' }], [{ value: null }]);
  assert.match(csv, /Факт\n$/);
});
