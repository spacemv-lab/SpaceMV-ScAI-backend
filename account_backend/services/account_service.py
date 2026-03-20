from typing import Any, Optional, cast
import secrets
import base64
import uuid

from libs.password import compare_password, hash_password
from datetime import datetime, timedelta
from models import db_session
from models.account import Account, AccountStatus
from services.errors.account import AccountLoginError, AccountNotFoundError, AccountPasswordError, AccountAlreadyExist


class WebAppAuthService:
    """Service for web app authentication."""

    @staticmethod
    def authenticate(name: str, password: str):
        """authenticate account with email and password"""
        session = db_session.create_session()
        try:
            account = session.query(Account).filter_by(name=name).first()
            if not account:
                raise AccountNotFoundError()

            passwordDb = account.password
            passwordSaltDb = account.password_salt
            pwdCorrect = compare_password(password, passwordDb, passwordSaltDb)

            return (
                pwdCorrect,
                str(account.id),
                account.name,
                account.email,
                int(account.coverage_analysis_permission or 0),
            )
        finally:
            db_session.close_session()

    @staticmethod
    def create_account(
            name: str,
            email: str,
            password: str
    ) -> dict:
        """create account"""
        session = db_session.create_session()
        try:
            account = session.query(Account).filter_by(name=name).first()
            if account:
                raise AccountAlreadyExist()

            account = Account()
            account.id = uuid.uuid4()
            account.name = name
            account.email = email

            salt = secrets.token_bytes(16)
            base64_salt = base64.b64encode(salt).decode()

            # encrypt password with salt
            password_hashed = hash_password(password, salt)
            base64_password_hashed = base64.b64encode(password_hashed).decode()

            account.password = base64_password_hashed
            account.password_salt = base64_salt
            account.status = 1
            account.coverage_analysis_permission = 0
            account.create_at = datetime.now()
            account.updated_at = datetime.now()

            session.add(account)
            session.commit()
            
            # Refresh to ensure all attributes are loaded before closing session
            session.refresh(account)
            
            # Get all needed attributes before closing session
            account_dict = {
                'id': str(account.id),
                'name': account.name,
                'email': account.email,
                'status': account.status,
                'coverage_analysis_permission': int(account.coverage_analysis_permission or 0),
            }
            
            return account_dict
        except Exception as e:
            session.rollback()
            raise e
        finally:
            db_session.close_session()
