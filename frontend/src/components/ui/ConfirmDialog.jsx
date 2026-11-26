import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import './ui.css';

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  danger = false,
  onConfirm,
  onCancel,
}) {
  useEffect(() => {
    if (!open) {
      return undefined;
    }
    const onKey = (event) => {
      if (event.key === 'Escape') {
        onCancel?.();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onCancel]);

  if (!open) {
    return null;
  }

  return createPortal(
    <div className="dialog-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="dialog__header">
          <h2 id="confirm-dialog-title">{title}</h2>
        </header>
        <div className="dialog__body">{message}</div>
        <footer className="dialog__footer">
          <button type="button" className="button button--ghost" onClick={onCancel}>{cancelLabel}</button>
          <button
            type="button"
            className={`button${danger ? ' button--danger' : ''}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </footer>
      </div>
    </div>,
    document.body,
  );
}
