from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import PROTECTED, AppSettings, Client, CurrentPrincipal, DbSession, error_responses
from app.core.config import Settings
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RegisterRequest, TokenResponse, UserProfile
from app.services.auth_service import AuthService, IssuedTokens

router = APIRouter(prefix="/auth", tags=["Авторизация"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, settings: Settings, tokens: IssuedTokens) -> None:
    response.set_cookie(
        REFRESH_COOKIE, tokens.refresh_token, expires=tokens.refresh_expires_at, path=REFRESH_COOKIE_PATH,
        httponly=True, secure=settings.refresh_cookie_secure, samesite="strict",
    )


def _token_response(response: Response, settings: Settings, tokens: IssuedTokens) -> TokenResponse:
    _set_refresh_cookie(response, settings, tokens)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.expires_in)


@router.post("/login", response_model=TokenResponse, summary="Вход по логину или email и паролю",
             description="Возвращает access-токен; refresh-токен устанавливается в httpOnly-cookie. "
                         "После 5 неудачных попыток подряд учётная запись блокируется на 15 минут.",
             responses=error_responses(401, 403, 422, 429))
def login(data: LoginRequest, response: Response, db: DbSession, settings: AppSettings, client: Client):
    tokens = AuthService(db, settings).login(data.login, data.password, client)
    return _token_response(response, settings, tokens)


@router.post("/refresh", response_model=TokenResponse, summary="Обновление access-токена",
             description="Использует refresh-токен из cookie и выдаёт новую пару токенов (ротация).",
             responses=error_responses(401))
def refresh(response: Response, db: DbSession, settings: AppSettings, client: Client,
            refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None):
    tokens = AuthService(db, settings).refresh(refresh_token, client)
    return _token_response(response, settings, tokens)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Завершение сеанса",
             description="Отзывает текущий сеанс: access- и refresh-токены этого входа перестают действовать.",
             responses=PROTECTED)
def logout(principal: CurrentPrincipal, db: DbSession, settings: AppSettings, client: Client):
    AuthService(db, settings).logout(principal.session, client)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True,
                           secure=settings.refresh_cookie_secure, samesite="strict")
    return response


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED,
             summary="Регистрация аналитика",
             description="Доступна, если ALLOW_REGISTRATION=true. Новый пользователь получает роль analyst.",
             responses=error_responses(403, 409, 422))
def register(data: RegisterRequest, db: DbSession, settings: AppSettings, client: Client):
    return UserProfile.model_validate(AuthService(db, settings).register(data, client))


@router.get("/me", response_model=UserProfile, summary="Профиль текущего пользователя", responses=PROTECTED)
def me(principal: CurrentPrincipal):
    return UserProfile.model_validate(principal.user)


@router.put("/me/password", status_code=status.HTTP_204_NO_CONTENT, summary="Смена пароля",
            description="Остальные сеансы пользователя завершаются.", responses=error_responses(401, 422))
def change_password(data: ChangePasswordRequest, principal: CurrentPrincipal, db: DbSession,
                    settings: AppSettings, client: Client):
    AuthService(db, settings).change_password(principal.session, data.current_password, data.new_password, client)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
