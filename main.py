from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.customer import Customer

app = FastAPI()

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()

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