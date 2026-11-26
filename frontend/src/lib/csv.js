function escapeCell(value) {
  if (value === null || value === undefined) {
    return '';
  }
  let text = String(value);
  // Формулы Excel (=, +, @ и «-» не перед числом). Обычные отрицательные числа не трогаем.
  if (/^[=+@]/.test(text) || /^-(?![0-9])/.test(text)) {
    text = `'${text}`;
  }
  if (/[;"\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

export function toCsv(columns, rows) {
  const header = columns.map((column) => escapeCell(column.title)).join(';');
  const lines = rows.map((row) => columns.map((column) => {
    const value = column.value ? column.value(row) : row[column.key];
    return escapeCell(value);
  }).join(';'));
  return `\uFEFF${[header, ...lines].join('\n')}`;
}

export function downloadText(filename, text, type = 'text/csv;charset=utf-8') {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function downloadBlob(filename, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
