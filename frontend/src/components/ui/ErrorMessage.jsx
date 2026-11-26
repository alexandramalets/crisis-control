import { IconWarning } from '../../icons/Icons.jsx';
import './ui.css';

export default function ErrorMessage({ message, onRetry }) {
  if (!message) {
    return null;
  }
  return (
    <div className="error-message" role="alert">
      <span className="error-message__icon"><IconWarning /></span>
      <div>{message}</div>
      {onRetry ? (
        <div className="error-message__actions">
          <button type="button" className="button button--ghost" onClick={onRetry}>Повторить</button>
        </div>
      ) : null}
    </div>
  );
}
