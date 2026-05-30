# app/models/user_session.py

from sqlalchemy import Column, Integer, String
from app.db.session import Base

class UserSession(Base):
    
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    refresh_token_hash = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)
    is_revoked = Column(Integer, default=0)
    created_at = Column(String, nullable=False)