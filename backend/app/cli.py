"""Административные команды.

Создание пользователя (например, первого администратора):
  python -m app.cli create-user --username admin --email admin@example.org --full-name "Администратор"
Пароль запрашивается дважды без отображения на экране. Для автоматизации пароль можно
передать через стандартный ввод: ... --password-stdin. Аргументом командной строки пароль
не принимается, чтобы он не попадал в историю команд и список процессов.
"""

import argparse
import getpass
import sys

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.services.access import ROLE_ADMIN, ROLES

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CONFIG_ERROR = 2
EXIT_DATABASE_UNAVAILABLE = 3


def _read_password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    password = getpass.getpass("Пароль: ")
    if password != getpass.getpass("Повторите пароль: "):
        raise ValueError("Пароли не совпадают")
    return password


def create_user(args: argparse.Namespace) -> int:
    from app.core.config import get_settings
    from app.db.session import describe_connection_error, get_session_factory
    from app.schemas.auth import RegisterRequest
    from app.services.errors import ServiceError
    from app.services.user_service import UserService

    try:
        get_settings()
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]).upper() for e in exc.errors())
        print(f"ОШИБКА: некорректная конфигурация: {fields}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    try:
        password = _read_password(args.password_stdin)
        data = RegisterRequest(username=args.username, email=args.email, full_name=args.full_name,
                               password=password)
    except ValueError as exc:
        from app.core.errors import validation_message

        messages = ([f"{e['loc'][0] if e['loc'] else 'данные'}: {validation_message(e)}" for e in exc.errors()]
                    if isinstance(exc, ValidationError) else [str(exc)])
        print("ОШИБКА: " + "; ".join(messages), file=sys.stderr)
        return EXIT_FAILED

    try:
        with get_session_factory()() as session:
            user = UserService(session).create_user(data.username, data.email, data.full_name,
                                                    data.password, args.role)
            session.commit()
    except ServiceError as exc:
        print(f"ОШИБКА: {exc.message}", file=sys.stderr)
        return EXIT_FAILED
    except OperationalError as exc:
        print(f"ОШИБКА: PostgreSQL недоступна ({describe_connection_error(exc)})", file=sys.stderr)
        return EXIT_DATABASE_UNAVAILABLE
    except ProgrammingError:
        print("ОШИБКА: схема БД не создана. Выполните python -m app.db.setup", file=sys.stderr)
        return EXIT_FAILED

    print(f"Пользователь {user.username} (id={user.id}, роль {args.role}) создан")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Административные команды")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="создать пользователя")
    create.add_argument("--username", required=True, help="логин: строчные латинские буквы, цифры, . _ -")
    create.add_argument("--email", required=True)
    create.add_argument("--full-name", required=True)
    create.add_argument("--role", choices=ROLES, default=ROLE_ADMIN)
    create.add_argument("--password-stdin", action="store_true", help="прочитать пароль из стандартного ввода")
    create.set_defaults(handler=create_user)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
