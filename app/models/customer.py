# app/models/customer.py

from sqlalchemy import Column, Integer, String
from app.db.session import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String)
    phone_number = Column(String)
    email = Column(String, unique=True, nullable=True)