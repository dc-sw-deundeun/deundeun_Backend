from sqlalchemy import Column, Integer

from app.database.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    # email, nickname, status, created_at, deleted_at — Phase 1에서 확정


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True)
    # user_id, password_hash, last_password_changed_at — Phase 1에서 확정


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True)


class PolicyConsent(Base):
    __tablename__ = "policy_consents"

    id = Column(Integer, primary_key=True)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
