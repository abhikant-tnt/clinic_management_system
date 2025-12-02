# Models & ORM Explained

## What is ORM?

**ORM = Object-Relational Mapping**

ORM is a technique that lets you interact with databases using **Python objects** instead of writing raw SQL queries.

## Current Approach (What You're Using Now)

You're currently using **raw SQL** and **direct database access**:

### SQLite (Raw SQL):
```python
# Current way - Writing SQL directly
sqlite_cursor.execute("SELECT name, age, phone FROM patients WHERE phone = ?", (phone,))
sqlite_cursor.execute("INSERT INTO patients (name, age, phone) VALUES (?, ?, ?)", (name, age, phone))
```

## ORM Approach (Alternative - For Future)

With ORM (like SQLAlchemy), you'd use **Python classes** instead:

### Example with SQLAlchemy ORM:
```python
# Instead of raw SQL, you'd define a Model class
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    age = Column(Integer)
    phone = Column(String, unique=True, nullable=False)
    registration_date = Column(String)
    billed_amount = Column(Float)
    outstanding_amount = Column(Float)

# Then use it like Python objects:
# Find patient
patient = session.query(Patient).filter(Patient.phone == phone).first()

# Create patient
new_patient = Patient(name="John", age=30, phone="1234567890")
session.add(new_patient)
session.commit()
```

## Comparison

| Aspect | Current (Raw SQL) | ORM (SQLAlchemy) |
|--------|------------------|------------------|
| **Code** | `sqlite_cursor.execute("SELECT...")` | `session.query(Patient).filter(...)` |
| **Type Safety** | ❌ No | ✅ Yes |
| **Auto-completion** | ❌ No | ✅ Yes |
| **SQL Injection** | ⚠️ Manual protection | ✅ Automatic |
| **Learning Curve** | ✅ Easy | ⚠️ Steeper |
| **Flexibility** | ✅ Full SQL control | ⚠️ Limited to ORM features |

## Why Keep the `models/` Folder?

The `app/models/` folder is **reserved for future use** if you decide to:

1. **Migrate to ORM** (SQLAlchemy, Tortoise ORM, etc.)
2. **Add database models** for better type safety
3. **Use database migrations** (Alembic with SQLAlchemy)
4. **Simplify complex queries** with ORM relationships

## When to Use ORM?

✅ **Use ORM when:**
- You want type safety and auto-completion
- You're building complex relationships (foreign keys, joins)
- You want automatic migrations
- Team prefers Python objects over SQL

❌ **Stick with Raw SQL when:**
- You need full SQL control
- Performance is critical
- You're comfortable with SQL
- Simple queries are sufficient

## Your Current Setup

You're using **raw SQL + PostgreSQL**, which is perfectly fine for:
- ✅ Simple queries
- ✅ Full control
- ✅ Easy to understand
- ✅ Good performance

The `models/` folder is there **if you want to upgrade later** - but you don't need to use it right now!

