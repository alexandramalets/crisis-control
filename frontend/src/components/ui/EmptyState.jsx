import './ui.css';

export default function EmptyState({ title, description, action }) {
  return (
    <div className="empty-state">
      {title ? <div className="empty-state__title">{title}</div> : null}
      {description ? <p>{description}</p> : null}
      {action}
    </div>
  );
}
