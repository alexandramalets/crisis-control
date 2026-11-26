import { Link } from 'react-router-dom';
import './pages.css';

export default function PrivacyPage() {
  return (
    <div className="page">
      <div>
        <h1>Политика конфиденциальности</h1>
        <p className="page__lead">
          Как в установленном экземпляре системы разделяются данные организаций и роли пользователей.
        </p>
      </div>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Назначение обработки</h2></header>
        <div className="card__body">
          <p>
            Система хранит показатели выбранной организации, проверяет загруженные таблицы и считает
            аналитические процедуры по запросу сотрудника этой организации.
          </p>
        </div>
      </section>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Разделение организаций</h2></header>
        <div className="card__body">
          <p>
            Аналитик видит только организации, владельцем которых является или к которым администратор
            явно назначил доступ. Наборы данных, исследования, отчёты, нормативы, мероприятия и сценарии
            другой организации недоступны: список их не содержит, прямая ссылка возвращает «не найдено».
          </p>
        </div>
      </section>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Роль администратора</h2></header>
        <div className="card__body">
          <p>
            Администратор управляет учётными записями, организациями и назначениями доступа.
            Он не открывает наборы показателей, не запускает исследования и не читает результаты анализа.
            Рабочая аналитика доступна только сотрудникам с ролью «аналитик» и назначенным доступом.
          </p>
        </div>
      </section>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Категории данных</h2></header>
        <div className="card__body">
          <ul className="issue-list">
            <li>Учётные записи: логин, адрес электронной почты, ФИО, роль, статус.</li>
            <li>Организации: название, описание, список сотрудников с уровнем доступа.</li>
            <li>Показатели и результаты исследований — только в пределах своей организации.</li>
            <li>Журнал действий без паролей и без содержимого исходных таблиц.</li>
          </ul>
        </div>
      </section>

      <section className="card">
        <header className="card__header"><h2 className="card__title">Хранение</h2></header>
        <div className="card__body">
          <p>
            Пароли хранятся в виде хэша. Исходные файлы на сервере шифруются.
            Удаление набора, исследования или мероприятия удаляет связанные записи в основной базе.
            Резервные копии, если их ведёт оператор инфраструктуры, живут по его регламенту.
          </p>
        </div>
      </section>

      <div className="page-actions">
        <Link className="button button--ghost" to="/help">Справка</Link>
        <Link className="button button--ghost" to="/login">Вход</Link>
      </div>
    </div>
  );
}
