import './ui.css';

export default function Notice({ tone = 'info', title, children }) {
  if (!title && !children) {
    return null;
  }
  return (
    <div className={`notice notice--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {title ? <strong>{title}</strong> : null}
      {children ? <div>{children}</div> : null}
    </div>
  );
}
