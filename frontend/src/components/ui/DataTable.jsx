import { useMemo, useState } from 'react';
import EmptyState from './EmptyState.jsx';
import './ui.css';

function cellValue(column, row) {
  if (column.sortValue) {
    return column.sortValue(row);
  }
  return row[column.key];
}

function formatCell(value) {
  if (value == null || typeof value === 'object') {
    return value == null ? '' : '—';
  }
  return value;
}

export default function DataTable({
  columns, rows, emptyTitle, emptyDescription, rowKey = 'id',
  sortable = false, filterable = false, filterPlaceholder = 'Фильтр…',
}) {
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const list = rows || [];
    const needle = query.trim().toLowerCase();
    if (!needle) {
      return list;
    }
    return list.filter((row) => columns.some((column) => {
      const value = cellValue(column, row);
      return value != null && String(value).toLowerCase().includes(needle);
    }));
  }, [rows, query, columns]);

  const visible = useMemo(() => {
    if (!sortKey) {
      return filtered;
    }
    const column = columns.find((item) => item.key === sortKey);
    const copy = [...filtered];
    copy.sort((left, right) => {
      const a = cellValue(column, left);
      const b = cellValue(column, right);
      if (a == null && b == null) {
        return 0;
      }
      if (a == null) {
        return 1;
      }
      if (b == null) {
        return -1;
      }
      if (typeof a === 'number' && typeof b === 'number') {
        return sortDir === 'asc' ? a - b : b - a;
      }
      return sortDir === 'asc'
        ? String(a).localeCompare(String(b), 'ru')
        : String(b).localeCompare(String(a), 'ru');
    });
    return copy;
  }, [filtered, sortKey, sortDir, columns]);

  function toggleSort(key) {
    if (!sortable) {
      return;
    }
    if (sortKey === key) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  }

  return (
    <div>
      {filterable ? (
        <div className="table-toolbar">
          <input
            className="input"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={filterPlaceholder}
            aria-label="Фильтр таблицы"
          />
        </div>
      ) : null}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key} style={column.width ? { width: column.width } : undefined}>
                  {sortable ? (
                    <button type="button" className="table-sort" onClick={() => toggleSort(column.key)}>
                      {column.title}
                      {sortKey === column.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                    </button>
                  ) : column.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {visible.length ? visible.map((row, index) => (
              <tr key={row[rowKey] ?? row.user_id ?? row.id ?? index}>
                {columns.map((column) => (
                  <td key={column.key}>
                    {column.render ? column.render(row) : formatCell(row[column.key])}
                  </td>
                ))}
              </tr>
            )) : (
              <tr>
                <td colSpan={columns.length} className="data-table__empty">
                  <EmptyState title={emptyTitle || 'Нет записей'} description={emptyDescription} />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
