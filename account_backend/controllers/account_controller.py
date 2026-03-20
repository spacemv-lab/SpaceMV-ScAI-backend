from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, HTTPException, Depends
import logging

from services.account_service import WebAppAuthService
from services.errors.account import AccountLoginError, AccountNotFoundError, AccountPasswordError, AccountAlreadyExist
from models.account import Account

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    name: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    code: int
    result: str
    msg: str
    data: dict


class RegisterRequest(BaseModel):
    name: str = Field(..., description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., description="密码")


class RegisterResponse(BaseModel):
    id: str
    name: str
    email: str
    status: int
    coverage_analysis_permission: int


router = APIRouter(prefix="/api", tags=["账户管理"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """User Login"""
    try:
        logger.info(f"Login attempt for user: {request.name}")
        pwd_correct, user_id, name, email, coverage_analysis_permission = WebAppAuthService.authenticate(
            name=request.name,
            password=request.password
        )
        
        if not pwd_correct:
            raise AccountPasswordError()
            
        return LoginResponse(
            code=200,
            result="success",
            msg="ok",
            data={
                "id": user_id,
                "name": name,
                "email": email,
                "coverage_analysis_permission": coverage_analysis_permission,
            }
        )
    except AccountNotFoundError:
        logger.error(f"Account not found: {request.name}")
        raise HTTPException(status_code=404, detail="账户不存在")
    except AccountPasswordError:
        logger.error(f"Password error for user: {request.name}")
        raise HTTPException(status_code=401, detail="密码错误")
    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/accountAdd", response_model=RegisterResponse)
async def accountAdd(request: RegisterRequest):
    """User Registration"""
    try:
        logger.info(f"Registration attempt for user: {request.name}")
        account_dict = WebAppAuthService.create_account(
            name=request.name,
            email=request.email,
            password=request.password
        )
        
        return RegisterResponse(
            id=account_dict['id'],
            name=account_dict['name'],
            email=account_dict['email'],
            status=account_dict['status'],
            coverage_analysis_permission=account_dict['coverage_analysis_permission'],
        )
    except AccountAlreadyExist:
        logger.error(f"Account already exists: {request.name}")
        raise HTTPException(status_code=400, detail="账户已存在")
    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))





