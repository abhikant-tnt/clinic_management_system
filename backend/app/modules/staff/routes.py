from fastapi import APIRouter, HTTPException, Query
from typing import List
from app.core.config import settings
from app.core.database import local_postgres_conn, local_postgres_cursor, db_session, sync_local_to_main
from app.core.models import StaffModel
from sqlalchemy import and_
from app.modules.staff.schemas import StaffCreate, StaffUpdate, Staff

router = APIRouter()

def get_tenant_id() -> str:
    return settings.TENANT_ID

def staff_to_dict(staff_data) -> dict:
    if isinstance(staff_data, dict):
        return staff_data
    return {
        "id": staff_data.id,
        "tenant_id": staff_data.tenant_id,
        "firstname": staff_data.firstname,
        "lastname": staff_data.lastname,
        "speciality": staff_data.speciality,
        "phone": staff_data.phone,
        "synced_to_main": staff_data.synced_to_main,
        "last_synced_at": staff_data.last_synced_at.isoformat() if staff_data.last_synced_at else None
    }

def check_staff_exists(staff_id: int, tenant_id: str) -> bool:
    if db_session:
        try:
            return db_session.query(StaffModel).filter(
                and_(StaffModel.id == staff_id, StaffModel.tenant_id == tenant_id)
            ).first() is not None
        except Exception:
            return False
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT id FROM staff WHERE id = %s AND tenant_id = %s", (staff_id, tenant_id))
            return local_postgres_cursor.fetchone() is not None
        except Exception:
            return False
    return False

def get_staff_by_id(staff_id: int, tenant_id: str):
    if db_session:
        try:
            return db_session.query(StaffModel).filter(
                and_(StaffModel.id == staff_id, StaffModel.tenant_id == tenant_id)
            ).first()
        except Exception:
            return None
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("""
                SELECT id, tenant_id, firstname, lastname, speciality, phone, synced_to_main, last_synced_at
                FROM staff WHERE id = %s AND tenant_id = %s
            """, (staff_id, tenant_id))
            record = local_postgres_cursor.fetchone()
            if record:
                columns = ["id", "tenant_id", "firstname", "lastname", "speciality", "phone", "synced_to_main", "last_synced_at"]
                return dict(zip(columns, record))
        except Exception:
            return None
    return None

@router.get("/")
def get_staff(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100)):
    tenant_id = get_tenant_id()
    sync_local_to_main()
    
    staff_list = []
    if db_session:
        try:
            staff = db_session.query(StaffModel).filter(StaffModel.tenant_id == tenant_id).all()
            staff_list = [staff_to_dict(s) for s in staff]
        except Exception as e:
            print(f"Error fetching staff (SQLAlchemy): {e}")
    elif local_postgres_cursor:
        try:
            local_postgres_cursor.execute("SELECT * FROM staff WHERE tenant_id = %s", (tenant_id,))
            columns = [desc[0] for desc in local_postgres_cursor.description]
            staff_list = [dict(zip(columns, r)) for r in local_postgres_cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching staff: {e}")
    
    staff_list.sort(key=lambda x: x.get("id", 0))
    total = len(staff_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "staff": staff_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
    }

@router.get("/{staff_id}")
def get_staff_member(staff_id: int):
    tenant_id = get_tenant_id()
    staff_data = get_staff_by_id(staff_id, tenant_id)
    if not staff_data:
        raise HTTPException(status_code=404, detail=f"Staff with ID {staff_id} not found for this tenant.")
    return staff_to_dict(staff_data)

@router.post("/")
def create_staff(staff_data: StaffCreate):
    tenant_id = get_tenant_id()
    tenant_id_to_use = staff_data.tenant_id if staff_data.tenant_id else tenant_id
    
    save_successful = False
    new_staff_id = None
    
    if db_session:
        try:
            existing = db_session.query(StaffModel).filter(
                and_(StaffModel.phone == staff_data.phone, StaffModel.tenant_id == tenant_id_to_use)
            ).first()
            if existing:
                raise HTTPException(status_code=400, detail="Staff with this phone number already exists for this tenant.")
            
            new_staff = StaffModel(
                tenant_id=tenant_id_to_use,
                firstname=staff_data.firstname.lower(),
                lastname=staff_data.lastname.lower(),
                speciality=staff_data.speciality.lower() if staff_data.speciality else None,
                phone=staff_data.phone,
                synced_to_main=False
            )
            db_session.add(new_staff)
            db_session.commit()
            db_session.refresh(new_staff)
            new_staff_id = new_staff.id
            print(f"Staff successfully saved using SQLAlchemy with ID {new_staff_id}.")
            save_successful = True
        except HTTPException:
            raise
        except Exception as e:
            db_session.rollback()
            print(f"SQLAlchemy save FAILED. Error: {str(e)}.")
            save_successful = False
    
    if not save_successful and local_postgres_cursor and local_postgres_conn:
        try:
            from app.core.database import ensure_tables_exist
            ensure_tables_exist()
            
            local_postgres_cursor.execute(
                "SELECT id FROM staff WHERE phone = %s AND tenant_id = %s",
                (staff_data.phone, tenant_id_to_use)
            )
            if local_postgres_cursor.fetchone():
                raise HTTPException(status_code=400, detail="Staff with this phone number already exists for this tenant.")
            
            local_postgres_cursor.execute("""
                INSERT INTO staff (tenant_id, firstname, lastname, speciality, phone, synced_to_main)
                VALUES (%s, %s, %s, %s, %s, FALSE)
                RETURNING id
            """, (
                tenant_id_to_use,
                staff_data.firstname.lower(),
                staff_data.lastname.lower(),
                staff_data.speciality.lower() if staff_data.speciality else None,
                staff_data.phone
            ))
            result = local_postgres_cursor.fetchone()
            new_staff_id = result[0] if result else None
            local_postgres_conn.commit()
            print(f"Staff successfully saved to Local PostgreSQL with ID {new_staff_id}.")
            save_successful = True
        except HTTPException:
            raise
        except Exception as e:
            print(f"Local PostgreSQL save FAILED. Error: {str(e)}.")
    
    if save_successful and new_staff_id:
        sync_local_to_main()
        return {"message": f"Staff created successfully with ID {new_staff_id}", "staff_id": new_staff_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create staff. Database connection not available.")

@router.put("/{staff_id}")
def update_staff(staff_id: int, staff_data: StaffUpdate):
    tenant_id = get_tenant_id()
    existing_staff_obj = get_staff_by_id(staff_id, tenant_id)
    if not existing_staff_obj:
        raise HTTPException(status_code=404, detail=f"Staff with ID {staff_id} not found for this tenant.")
    
    update_data = {}
    if staff_data.firstname is not None:
        update_data["firstname"] = staff_data.firstname.lower()
    if staff_data.lastname is not None:
        update_data["lastname"] = staff_data.lastname.lower()
    if staff_data.speciality is not None:
        update_data["speciality"] = staff_data.speciality.lower()
    if staff_data.phone is not None:
        update_data["phone"] = staff_data.phone
    update_data["synced_to_main"] = False
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    
    postgres_updated = False
    if db_session:
        try:
            staff = db_session.query(StaffModel).filter(
                and_(StaffModel.id == staff_id, StaffModel.tenant_id == tenant_id)
            ).first()
            if not staff:
                raise HTTPException(status_code=404, detail=f"Staff with ID {staff_id} not found for this tenant.")
            for key, value in update_data.items():
                setattr(staff, key, value)
            db_session.commit()
            db_session.refresh(staff)
            print(f"Local PostgreSQL staff ID {staff_id} updated.")
            postgres_updated = True
        except HTTPException:
            raise
        except Exception as e:
            db_session.rollback()
            print(f"SQLAlchemy update FAILED. Error: {str(e)}.")
    elif local_postgres_cursor and local_postgres_conn:
        try:
            set_clauses = []
            values = []
            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)
            values.append(staff_id)
            values.append(tenant_id)
            
            query = f"UPDATE staff SET {', '.join(set_clauses)} WHERE id = %s AND tenant_id = %s"
            local_postgres_cursor.execute(query, values)
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount > 0:
                print(f"Local PostgreSQL staff ID {staff_id} updated.")
                postgres_updated = True
        except Exception as e:
            print(f"Local PostgreSQL Update FAILED. Error: {str(e)}.")
    
    if postgres_updated:
        sync_local_to_main()
        return {"message": f"Staff with ID {staff_id} updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update staff. Database connection not available.")

@router.delete("/{staff_id}")
def delete_staff(staff_id: int):
    tenant_id = get_tenant_id()
    postgres_deleted = False
    
    if db_session:
        try:
            staff = db_session.query(StaffModel).filter(
                and_(StaffModel.id == staff_id, StaffModel.tenant_id == tenant_id)
            ).first()
            if staff:
                db_session.delete(staff)
                db_session.commit()
                print(f"Staff with ID {staff_id} deleted successfully.")
                postgres_deleted = True
            else:
                print(f"Staff with ID {staff_id} not found for deletion.")
        except Exception as e:
            db_session.rollback()
            print(f"Error deleting staff: {e}.")
    elif local_postgres_cursor and local_postgres_conn:
        try:
            local_postgres_cursor.execute("DELETE FROM staff WHERE id = %s AND tenant_id = %s", (staff_id, tenant_id))
            local_postgres_conn.commit()
            if local_postgres_cursor.rowcount > 0:
                print(f"Staff with ID {staff_id} deleted from Local PostgreSQL.")
                postgres_deleted = True
            else:
                print(f"Staff with ID {staff_id} not found in Local PostgreSQL for deletion.")
        except Exception as e:
            print(f"Error deleting staff from Local PostgreSQL: {e}.")
    
    if postgres_deleted:
        sync_local_to_main()
        return {"message": f"Staff with ID {staff_id} deleted successfully from Local PostgreSQL."}
    else:
        raise HTTPException(status_code=404, detail=f"Staff with ID {staff_id} not found for this tenant.")

