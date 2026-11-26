import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  return (
    <div className="page">
      <h1>Страница не найдена</h1>
      <p className="page__lead">Проверьте адрес или вернитесь на главную панель.</p>
      <Link to="/" className="button button--ghost">На главную</Link>
    </div>
  );
}
