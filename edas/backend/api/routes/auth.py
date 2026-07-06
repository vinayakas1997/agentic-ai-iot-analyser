from fastapi import APIRouter

from api.auth import Token, UserCreate, UserLogin, authenticate_user, create_access_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
async def register(body: UserCreate) -> Token:
    user = await register_user(body.email, body.password)
    token = create_access_token(str(user.id))
    return Token(access_token=token, user_id=str(user.id))


@router.post("/login", response_model=Token)
async def login(body: UserLogin) -> Token:
    user = await authenticate_user(body.email, body.password)
    token = create_access_token(str(user.id))
    return Token(access_token=token, user_id=str(user.id))
