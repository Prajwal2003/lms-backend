from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Tuple

from app.db.session import SessionLocal
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.customer import Customer
from app.models.users import Users
from app.models.user_session import UserSession

app = FastAPI()
bearer_scheme = HTTPBearer()

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

def require_role(required_role: str):
    def _require_role(
        current_user: Users = Depends(get_current_user)
    ):
        if current_user.role.lower() != required_role:
            raise HTTPException(status_code=403, detail=f"{required_role.capitalize()} access required")

        return current_user

    return _require_role

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    current_user, _ = get_current_user_session(credentials, db)
    return current_user

def get_current_user_session(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> Tuple[Users, UserSession]:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid access token")

    try:
        user_id = int(payload.get("sub"))
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid access token")

    user_session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id)
        .filter(UserSession.user_id == user_id)
        .first()
    )

    if not user_session or user_session.is_revoked:
        raise HTTPException(status_code=401, detail="Invalid session")

    user = db.query(Users).filter(Users.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")

    return user, user_session

@app.get("/")
async def root():
    return {"message": "LMS Backend Running"}

@app.get("/db-check")
def db_check():
    db = SessionLocal()

    try:
        result = db.execute(text("SELECT 1"))
        return {
            "status": "connected"
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
    finally:
        db.close()

@app.get("/customers")
def get_customers(
    db: Session = Depends(get_db)
):
    customers = db.query(Customer).all()

    return customers

@app.get("/customers/{customer_id}")
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db)
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        return {"message": "Customer not found"}

    return customer

@app.post("/customers")
def create_customer(
    name: str,
    address: str,
    phone_number: str,
    db: Session = Depends(get_db)
):
    customer = Customer(
        name=name,
        address=address,
        phone_number=phone_number
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)

    return customer

@app.put("/customers/{customer_id}")
def update_customer(
    customer_id: int,
    name: str,
    address: str,
    phone_number: str,
    db: Session = Depends(get_db)
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        return {"message": "Customer not found"}

    customer.name = name
    customer.address = address
    customer.phone_number = phone_number

    db.commit()
    db.refresh(customer)

    return customer

@app.delete("/customers/{customer_id}")
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db)
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id)
        .first()
    )

    if not customer:
        return {"message": "Customer not found"}

    db.delete(customer)
    db.commit()

    return {
        "message": "Customer deleted"
    }

@app.post("/auth/register")
def register_user(
    name: str,
    email: str,
    password: str,
    role: str,
    db: Session = Depends(get_db)
):
    existing_user = db.query(Users).filter(Users.email == email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = hash_password(password)

    if role.lower() not in ["admin", "student", "teacher"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = Users(
        name=name,
        email=email.lower(),
        password_hash=password_hash,
        role=role,
        is_active=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

@app.post("/auth/login")
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    email = form_data.username
    password = form_data.password

    user = db.query(Users).filter(Users.email == email.lower()).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)

    user_session = UserSession(
        user_id=user.id,
        refresh_token_hash="",
        expires_at=expires_at,
        is_revoked=0,
        created_at=datetime.now(timezone.utc)
    )

    db.add(user_session)
    db.flush()

    access_token = create_access_token(user.id, user.email, user.role, session_id=user_session.id)
    refresh_token = create_refresh_token(user.id, session_id=user_session.id)
    user_session.refresh_token_hash = hash_token(refresh_token)

    db.commit()
    db.refresh(user_session)

    return {
        "email": user.email,
        "user_id": user.id,
        "session_id": user_session.id,
        "token_type": "bearer",
        "access_token": access_token,
        "refresh_token": refresh_token
    }

@app.delete("/delete-user/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Users = Depends(require_role("admin"))
):
    user = db.query(Users).filter(Users.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()

    return {
        "message": "User deleted"
    }

@app.post("/auth/refresh")
def refresh_access_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    payload = decode_token(refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    try:
        user_id = int(payload.get("sub"))
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id)
        .filter(UserSession.user_id == user_id)
        .first()
    )

    if not user_session or user_session.is_revoked:
        raise HTTPException(status_code=401, detail="Invalid session")

    if user_session.refresh_token_hash != hash_token(refresh_token):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(Users).filter(Users.id == user_session.user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")

    access_token = create_access_token(user.id, email=user.email, role=user.role, session_id=user_session.id)
    new_refresh_token = create_refresh_token(user.id, session_id=user_session.id)
    user_session.refresh_token_hash = hash_token(new_refresh_token)
    user_session.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()

    return {
        "user_id": user.id,
        "session_id": user_session.id,
        "token_type": "bearer",
        "access_token": access_token,
        "refresh_token": new_refresh_token
    }

@app.post("/auth/get-current-user")
def read_current_user(
    current_user: Users = Depends(get_current_user)
):
    return current_user

@app.post("/auth/logout")
def logout_user(
    db: Session = Depends(get_db),
    current_auth: Tuple[Users, UserSession] = Depends(get_current_user_session)
):
    current_user, current_session = current_auth
    current_session.is_revoked = 1

    db.commit()

    return {
        "message": "Logged out from this device"
    }
