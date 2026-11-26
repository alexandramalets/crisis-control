"""Дымовая проверка развёрнутого API через клиентский узел (nginx).

Нужны два пользователя-аналитика с одним паролем (создаются командой
python -m app.cli create-user ... --role analyst). Пароль передаётся через переменную
окружения SMOKE_PASSWORD, чтобы не попадать в историю команд.

  python scripts/smoke_api.py --base-url http://localhost:8080 --owner e2e.owner --other e2e.other
"""

import argparse
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--other", required=True)
    args = parser.parse_args()
    password = os.environ.get("SMOKE_PASSWORD")
    if not password:
        print("Задайте пароль в переменной окружения SMOKE_PASSWORD", file=sys.stderr)
        return 2

    api = httpx.Client(base_url=f"{args.base_url}/api/v1", timeout=10)
    results: list[tuple[str, int, int]] = []

    def check(name: str, response: httpx.Response, expected: int) -> httpx.Response:
        results.append((name, response.status_code, expected))
        return response

    def login(username: str) -> dict:
        response = check(f"Вход ({username})", api.post("/auth/login", json={"login": username, "password": password}), 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    check("Состояние сервиса", api.get("/health/ready"), 200)
    check("Вход с неверным паролем", api.post("/auth/login", json={"login": args.owner, "password": "wrong"}), 401)
    owner = login(args.owner)
    other = login(args.other)
    check("Профиль текущего пользователя", api.get("/auth/me", headers=owner), 200)
    check("Запрос без токена", api.get("/auth/me"), 401)
    check("Некорректный токен", api.get("/auth/me", headers={"Authorization": "Bearer abc.def.ghi"}), 401)

    organization = check("Создание организации",
                         api.post("/organizations", json={"name": "Демонстрационная организация"}, headers=owner), 201)
    organization_id = organization.json()["id"]
    values = [{"indicator_code": "revenue", "period_start": f"2024-{m:02d}-01", "value": str(1000 + m)}
              for m in range(1, 7)]
    dataset = check("Создание набора данных", api.post(
        f"/organizations/{organization_id}/datasets",
        json={"name": "Синтетический набор", "granularity": "month", "values": values}, headers=owner), 201)
    dataset_id = dataset.json()["id"]
    check("Получение своего набора", api.get(f"/datasets/{dataset_id}", headers=owner), 200)
    check("Список своих наборов", api.get("/datasets", headers=owner), 200)
    check("Чужой набор данных", api.get(f"/datasets/{dataset_id}", headers=other), 404)
    check("Удаление чужого набора", api.delete(f"/datasets/{dataset_id}", headers=other), 404)
    foreign_list = check("Список наборов другого пользователя", api.get("/datasets", headers=other), 200)
    results.append(("  …в нём нет чужих наборов", 200 if foreign_list.json()["total"] == 0 else 500, 200))
    check("Список исследований", api.get("/analyses", headers=owner), 200)
    check("Список отчётов", api.get("/reports", headers=owner), 200)
    check("Удаление своего набора", api.delete(f"/datasets/{dataset_id}", headers=owner), 204)
    check("Удаление организации", api.delete(f"/organizations/{organization_id}", headers=owner), 204)
    check("Выход", api.post("/auth/logout", headers=owner), 204)
    check("Токен после выхода", api.get("/auth/me", headers=owner), 401)
    check("Выход второго пользователя", api.post("/auth/logout", headers=other), 204)

    failed = 0
    for name, actual, expected in results:
        mark = "OK  " if actual == expected else "FAIL"
        failed += actual != expected
        print(f"{mark} {actual} (ожидалось {expected})  {name}")
    print(f"Итого: {len(results) - failed} из {len(results)} проверок пройдено")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
