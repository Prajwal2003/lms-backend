# app/models/users.py

from sqlalchemy import Column, Integer, String
from app.db.session import Base

class Users(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)