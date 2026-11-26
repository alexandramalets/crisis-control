const NUMBER = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });
const INTEGER = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 });
const DATETIME = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' });
const DATE = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' });

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return '—';
  }
  return new Intl.NumberFormat('ru-RU', { maximumFractionDigits: digits }).format(number);
}

export function formatMoney(value, unit = 'руб.') {
  if (value === null || value === undefined || value === '') {
    return '—';
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return '—';
  }
  const abs = Math.abs(number);
  const formatter = abs >= 1000 ? INTEGER : NUMBER;
  return `${formatter.format(number)} ${unit}`.trim();
}

export function formatPercent(value, { signed = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  const number = Number(value);
  const formatted = NUMBER.format(number);
  if (signed && number > 0) {
    return `+${formatted} %`;
  }
  return `${formatted} %`;
}

export function formatDate(value) {
  if (!value) {
    return '—';
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return DATE.format(date);
}

export function formatDateTime(value) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return DATETIME.format(date);
}

export function analysisStatusLabel(status) {
  return {
    queued: 'В очереди',
    running: 'Выполняется',
    completed: 'Завершено',
    partially_completed: 'Частично завершено',
    failed: 'Ошибка',
  }[status] || status || '—';
}

export function interpretScore(score) {
  if (score == null || Number.isNaN(Number(score))) {
    return null;
  }
  const value = Number(score);
  if (value >= 75) {
    return 'Устойчивое состояние';
  }
  if (value >= 50) {
    return 'Умеренный риск';
  }
  if (value >= 25) {
    return 'Повышенный риск';
  }
  return 'Выраженные признаки риска';
}

export function scoreTone(score) {
  if (score == null || Number.isNaN(Number(score))) {
    return 'var(--color-text-muted)';
  }
  const value = Number(score);
  if (value >= 75) {
    return 'var(--color-positive)';
  }
  if (value >= 50) {
    return 'var(--color-warning)';
  }
  return 'var(--color-negative)';
}

export function procedureLabel(type) {
  return {
    preprocessing: 'Проверка данных',
    anomalies: 'Аномалии',
    trends: 'Тенденции',
    correlation: 'Корреляции',
    clustering: 'Кластеры',
    forecasting: 'Прогноз',
    assessment: 'Сводная оценка',
    ratios: 'Коэффициенты',
    ok: 'Выполнено',
    skipped: 'Пропущено',
    error: 'Ошибка',
    pending: 'Ожидание',
  }[type] || type || '—';
}

export function accessLevelLabel(level) {
  return level === 'edit' ? 'Редактирование' : 'Просмотр';
}

export function auditActionLabel(action) {
  return {
    login: 'Вход',
    logout: 'Выход',
    analysis_started: 'Запуск исследования',
    analysis_deleted: 'Удаление исследования',
    dataset_created: 'Создание набора',
    dataset_imported: 'Загрузка набора',
    dataset_deleted: 'Удаление набора',
    organization_created: 'Создание организации',
    organization_deleted: 'Удаление организации',
    organization_access_granted: 'Назначение доступа',
    organization_access_updated: 'Изменение доступа',
    organization_access_revoked: 'Отзыв доступа',
    organization_workspace_cleared: 'Очистка рабочего пространства',
    recommendation_updated: 'Изменение рекомендации',
    measure_created: 'Создание мероприятия',
    measure_updated: 'Изменение мероприятия',
    measure_deleted: 'Удаление мероприятия',
    norm_updated: 'Изменение плана',
    threshold_updated: 'Изменение норматива',
    scenario_created: 'Создание сценария',
  }[action] || action || '—';
}
