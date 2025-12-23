from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List
from app.core.config import settings
from app.core.database import postgres_conn, postgres_cursor, db_session
from app.core.models import StaffModel
from sqlalchemy import and_
from app.modules.staff.schemas import StaffCreate, StaffUpdate, Staff
from app.core.dependencies import get_current_active_user

router = APIRouter()

def get_tenant_id() -> str:
    return settings.TENANT_ID

def staff_to_dict(staff_data) -> dict:
    if isinstance(staff_data, dict):
        return staff_data
    result = {
        "id": staff_data.id,
        "tenant_id": staff_data.tenant_id,
        "firstname": staff_data.firstname,
        "lastname": staff_data.lastname,
        "speciality": staff_data.speciality,
        "phone": staff_data.phone,
    }
    # Add user_type if available
    if hasattr(staff_data, 'user_type'):
        result["user_type"] = staff_data.user_type
    return result

def check_staff_exists(staff_id: int, tenant_id: str) -> bool:
    if db_session:
        try:
            return db_session.query(StaffModel).filter(
                and_(StaffModel.id == staff_id, StaffModel.tenant_id == tenant_id)
            ).first() is not None
        except Exception:
            return False
    elif postgres_cursor:
        try:
            postgres_cursor.execute("SELECT id FROM staff WHERE id = %s AND tenant_id = %s", (staff_id, tenant_id))
            return postgres_cursor.fetchone() is not None
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
    elif postgres_cursor:
        try:
            postgres_cursor.execute("""
                SELECT id, tenant_id, firstname, lastname, speciality, phone
                FROM staff WHERE id = %s AND tenant_id = %s
            """, (staff_id, tenant_id))
            record = postgres_cursor.fetchone()
            if record:
                columns = ["id", "tenant_id", "firstname", "lastname", "speciality", "phone"]
                return dict(zip(columns, record))
        except Exception:
            return None
    return None

@router.get("/")
def get_staff(
    page: int = Query(1, ge=1), 
    limit: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_active_user)
):
    """Get all staff (excludes admin). Requires authentication."""
    tenant_id = get_tenant_id()
    
    staff_list = []
    if db_session:
        try:
            staff = db_session.query(StaffModel).filter(
                and_(
                    StaffModel.tenant_id == tenant_id,
                    StaffModel.user_type != 'admin'
                )
            ).all()
            staff_list = [staff_to_dict(s) for s in staff]
        except Exception as e:
            pass
    elif postgres_cursor:
        try:
            postgres_cursor.execute(
                "SELECT id, tenant_id, firstname, lastname, speciality, phone, user_type FROM staff WHERE tenant_id = %s AND user_type != 'admin'", 
                (tenant_id,)
            )
            columns = [desc[0] for desc in postgres_cursor.description]
            staff_list = [dict(zip(columns, r)) for r in postgres_cursor.fetchall()]
        except Exception:
            pass
    
    staff_list.sort(key=lambda x: x.get("id", 0))
    total = len(staff_list)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    
    return {
        "staff": staff_list[(page - 1) * limit:page * limit],
        "pagination": {"total": total, "page": page, "limit": limit, "total_pages": total_pages, "has_next": page < total_pages, "has_prev": page > 1}
    }

@router.get("/{staff_id}")
def get_staff_member(
    staff_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """Get staff member by ID (blocks admin). Requires authentication."""
    tenant_id = get_tenant_id()
    staff_data = get_staff_by_id(staff_id, tenant_id)
    if not staff_data:
        raise HTTPException(status_code=404, detail=f"Staff with ID {staff_id} not found for this tenant.")
    
    # Check if trying to fetch admin
    if isinstance(staff_data, dict):
        user_type = staff_data.get("user_type")
    else:
        user_type = staff_data.user_type if hasattr(staff_data, 'user_type') else None
    
    if user_type == 'admin':
        raise HTTPException(status_code=404, detail=f"Staff with ID {staff_id} not found for this tenant.")
    
    return staff_to_dict(staff_data)

@router.post("/")
def create_staff(
    staff_data: StaffCreate,
    current_user: dict = Depends(get_current_active_user)
):
    """Create staff member. Requires authentication."""
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
            )
            db_session.add(new_staff)
            db_session.commit()
            db_session.refresh(new_staff)
            new_staff_id = new_staff.id
            save_successful = True
        except HTTPException:
            raise
        except Exception:
            db_session.rollback()
            save_successful = False
    
    if not save_successful and postgres_cursor and postgres_conn:
        try:
            from app.core.database import ensure_tables_exist
            ensure_tables_exist()
            
            postgres_cursor.execute(
                "SELECT id FROM staff WHERE phone = %s AND tenant_id = %s",
                (staff_data.phone, tenant_id_to_use)
            )
            if postgres_cursor.fetchone():
                raise HTTPException(status_code=400, detail="Staff with this phone number already exists for this tenant.")
            
            postgres_cursor.execute("""
                INSERT INTO staff (tenant_id, firstname, lastname, speciality, phone)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_id_to_use,
                staff_data.firstname.lower(),
                staff_data.lastname.lower(),
                staff_data.speciality.lower() if staff_data.speciality else None,
                staff_data.phone
            ))
            result = postgres_cursor.fetchone()
            new_staff_id = result[0] if result else None
            postgres_conn.commit()
            save_successful = True
        except HTTPException:
            raise
        except Exception:
            pass
    
    if save_successful and new_staff_id:
        return {"message": f"Staff created successfully with ID {new_staff_id}", "staff_id": new_staff_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create staff. Database connection not available.")

@router.put("/{staff_id}")
def update_staff(
    staff_id: int, 
    staff_data: StaffUpdate,
    current_user: dict = Depends(get_current_active_user)
):
    """Update staff member (allows updating admin). Requires authentication."""
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
            postgres_updated = True
        except HTTPException:
            raise
        except Exception:
            db_session.rollback()
    elif postgres_cursor and postgres_conn:
        try:
            set_clauses = []
            values = []
            for key, value in update_data.items():
                set_clauses.append(f"{key} = %s")
                values.append(value)
            values.append(staff_id)
            values.append(tenant_id)
            
            query = f"UPDATE staff SET {', '.join(set_clauses)} WHERE id = %s AND tenant_id = %s"
            postgres_cursor.execute(query, values)
            postgres_conn.commit()
            if postgres_cursor.rowcount > 0:
                postgres_updated = True
        except Exception:
            pass
    
    if postgres_updated:
        return {"message": f"Staff with ID {staff_id} updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update staff. Database connection not available.")

@router.delete("/{staff_id}")
def delete_staff(
    staff_id: int,
    current_user: dict = Depends(get_current_active_user)
):
    """Delete staff member (blocks deleting admin). Requires authentication."""
    tenant_id = get_tenant_id()
    
    # Check if trying to delete admin
    staff_data = get_staff_by_id(staff_id, tenant_id)
    if staff_data:
        if isinstance(staff_data, dict):
            user_type = staff_data.get("user_type")
        else:
            user_type = staff_data.user_type if hasattr(staff_data, 'user_type') else None
        
        if user_type == 'admin':
            raise HTTPException(
                status_code=403, 
                detail="Cannot delete admin user"
            )
    
    postgres_deleted = False
    
    if db_session:
        try:
            staff = db_session.query(StaffModel).filter(
                and_(StaffModel.id == staff_id, StaffModel.tenant_id == tenant_id)
            ).first()
            if staff:
                db_session.delete(staff)
                db_session.commit()
                postgres_deleted = True
        except Exception:
            db_session.rollback()
    elif postgres_cursor and postgres_conn:
        try:
            postgres_cursor.execute("DELETE FROM staff WHERE id = %s AND tenant_id = %s", (staff_id, tenant_id))
            postgres_conn.commit()
            if postgres_cursor.rowcount > 0:
                postgres_deleted = True
        except Exception:
            pass
    
    if postgres_deleted:
        return {"message": f"Staff with ID {staff_id} deleted successfully from PostgreSQL."}
    else:
        raise HTTPException(status_code=404, detail=f"Staff with ID {staff_id} not found for this tenant.")

