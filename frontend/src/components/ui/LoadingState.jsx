import './ui.css';

export default function LoadingState({ title = 'Загрузка…', description }) {
  return (
    <div className="loading-state" role="status">
      <div className="loading-state__title">{title}</div>
      {description ? <p>{description}</p> : null}
    </div>
  );
}
