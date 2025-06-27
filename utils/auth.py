from fastapi import HTTPException, status, Request, Response, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError, jwt
from datetime import datetime, timedelta
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, TOKEN_REFRESH_THRESHOLD_MINUTES
from db.db_ops import get_user, update_user_token
from service.xbx_api import XbxAPI
from utils.constant import PREFIX
from utils.gcode import verify_google_code
from typing import Optional
from fastapi.security import OAuth2PasswordBearer
import json

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/{PREFIX}/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def is_token_near_expiry(token: str) -> bool:
    """检查token是否即将过期（剩余时间少于阈值）"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        exp_timestamp = payload.get("exp")
        if not exp_timestamp:
            return True  # 没有过期时间，认为需要刷新

        exp_datetime = datetime.utcfromtimestamp(exp_timestamp)
        current_datetime = datetime.utcnow()
        time_remaining = exp_datetime - current_datetime

        # 如果剩余时间少于阈值，返回True
        return time_remaining.total_seconds() < (TOKEN_REFRESH_THRESHOLD_MINUTES * 60)
    except (JWTError, ValueError):
        return True  # 解析失败，认为需要刷新


def google_login(google_secret_key: Optional[str], code: str):
    google_secret = None
    user = get_user()
    if user:
        google_secret = user.secret
    if google_secret is None:
        # 首次登录，需前端传 google_secret_key 和 code
        if not google_secret_key or not code:
            raise HTTPException(status_code=400, detail="首次登录需提供google_secret_key和code")
        if not verify_google_code(google_secret_key, code):
            raise HTTPException(status_code=400, detail="Google验证码错误")
    else:
        # 后续登录，只需传 code
        if not verify_google_code(google_secret, code):
            raise HTTPException(status_code=400, detail="Google验证码错误")
    # 登录成功，生成token
    access_token = create_access_token(data={"sub": "google_user"})
    return {"access_token": access_token, "token_type": "Bearer"}


def verify_token(token: str):
    """验证token并返回用户信息"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="WebUI会话已到期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user = get_user()
        if not user or user.token != token:
            raise credentials_exception
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return {"username": username, "token": token}
    except JWTError:
        raise credentials_exception


def get_current_user(request: Request, response: Response, token: str = Depends(oauth2_scheme)):
    """获取当前用户（保留兼容性，但推荐使用中间件）"""
    user_info = verify_token(token)

    # 只在token即将过期时才刷新
    if is_token_near_expiry(token):
        new_token = create_access_token(data={"sub": user_info["username"]})
        response.headers["X-Refresh-Token"] = new_token
        update_user_token(new_token)
        return {"username": user_info["username"], "token": new_token}

    return {"username": user_info["username"], "token": token}


def get_current_user_from_request(request: Request):
    """从请求中获取当前用户信息（通过中间件设置）"""
    if hasattr(request.state, 'current_user'):
        return request.state.current_user
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件，统一处理token校验和刷新"""

    # 不需要认证的路径
    SKIP_AUTH_PATHS = {
        f"/{PREFIX}/first",
        f"/{PREFIX}/login",
        f"/{PREFIX}/declaration",
    }

    # wx用户信息不进行验证的路径
    SKIP_AUTH_USER_PATHS = {
        f"/{PREFIX}/user/info",
        f"/{PREFIX}/logout",
    }

    async def dispatch(self, request: Request, call_next):
        # 跳过不需要认证的路径
        if request.url.path in self.SKIP_AUTH_PATHS:
            return await call_next(request)

        # 检查是否有Authorization头
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            return Response(
                content=json.dumps({"msg": "未提供认证token", "code": 401}),
                status_code=401,
                media_type="application/json"
            )

        # 提取token
        token = authorization.split(" ")[1]

        try:
            # 验证token（只捕获认证相关异常）
            user_info = verify_token(token)

            # 将用户信息添加到request.state中，供后续使用
            request.state.current_user = user_info

        except HTTPException as e:
            # 认证相关的HTTPException
            return Response(
                content=json.dumps({"msg": e.detail, "code": e.status_code}),
                status_code=e.status_code,
                media_type="application/json"
            )
        except (JWTError, ValueError) as e:
            # JWT解析相关异常
            return Response(
                content=json.dumps({"msg": "token无效", "code": 401}),
                status_code=401,
                media_type="application/json"
            )

        # 如果不是绑定用户的接口，都需要验证一下 wx 是否过期
        if request.url.path not in self.SKIP_AUTH_USER_PATHS:
            try:
                api = XbxAPI.get_instance()
                api._ensure_token()
            except Exception as e:
                return Response(
                    content=json.dumps({"msg": "WX用户信息失效，请重新扫描二维码绑定用户", "code": 444}),
                    status_code=444,
                    media_type="application/json"
                )


        # 调用下一个处理器（业务逻辑异常会正常抛出）
        response = await call_next(request)

        # 只在请求成功处理且token即将过期时才刷新token
        if response.status_code < 400 and is_token_near_expiry(token):
            new_token = create_access_token(data={"sub": user_info["username"]})
            response.headers["X-Refresh-Token"] = new_token
            update_user_token(new_token)

        return response
 