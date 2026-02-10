from fastapi import HTTPException,APIRouter
from sqlalchemy import and_
from app.core.db_utils import get_db_session
from app.modules.asset_management.models import RoomModel, MachineModel
from app.core.config import settings
from app.modules.asset_management.schemas import RoomCreate, MachineCreate


router = APIRouter()


def get_tenant_id() -> str:
    return settings.TENANT_ID

def room_to_dict(room: RoomModel) -> dict:
    return {
        "id": room.id,
        "room_id": room.id, # Support both for compatibility
        "tenant_id": room.tenant_id,
        "room_number": room.room_number,
        "room_type": room.room_type,
        "is_available": room.is_available
    }

def machine_to_dict(machine: MachineModel) -> dict:
    return {
        "id": machine.id,
        "machine_id": machine.id, # Support both for compatibility
        "tenant_id": machine.tenant_id,
        "name": machine.name,
        "status": machine.status,
        "room_id": machine.room_id
    }

# --- ROOM CRUD ---
@router.get("/rooms")
async def get_rooms():
    try:
        with get_db_session() as session:
            rooms = session.query(RoomModel).filter(
                RoomModel.tenant_id == get_tenant_id()
            ).all()
            return [room_to_dict(r) for r in rooms]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching rooms: {str(e)}")

@router.post("/rooms")
async def create_room(data: RoomCreate):
    tenant_id = get_tenant_id()
    try:
        with get_db_session() as session:
            new_room = RoomModel(
                tenant_id=tenant_id,
                room_number=data.room_number,
                room_type=data.room_type,
                is_available=True
            )
            session.add(new_room)
            session.commit()
            session.refresh(new_room)
            return {
                "message": "Room created successfully",
                "room_id": new_room.id,
                "room": room_to_dict(new_room)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create room: {str(e)}")

@router.put("/rooms/{room_id}")
async def update_room(room_id: int, data: RoomCreate):
    tenant_id = get_tenant_id()
    try:
        with get_db_session() as session:
            room = session.query(RoomModel).filter(
                and_(RoomModel.id == room_id, RoomModel.tenant_id == tenant_id)
            ).first()
            if not room:
                raise HTTPException(status_code=404, detail="Room not found")
            
            if data.room_number is not None: room.room_number = data.room_number
            if data.room_type is not None: room.room_type = data.room_type
            
            session.commit()
            session.refresh(room)
            return {
                "message": "Room updated successfully",
                "room": room_to_dict(room)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@router.delete("/rooms/{room_id}")
async def delete_room(room_id: int):
    tenant_id = get_tenant_id()
    try:
        with get_db_session() as session:
            room = session.query(RoomModel).filter(
                and_(RoomModel.id == room_id, RoomModel.tenant_id == tenant_id)
            ).first()
            if not room:
                raise HTTPException(status_code=404, detail="Room not found")
            session.delete(room)
            session.commit()
            return {"message": f"Room with ID {room_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

# --- MACHINE CRUD ---
@router.get("/machines")
async def get_machines():
    try:
        with get_db_session() as session:
            machines = session.query(MachineModel).filter(
                MachineModel.tenant_id == get_tenant_id()
            ).all()
            return [machine_to_dict(m) for m in machines]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching machines: {str(e)}")

@router.post("/machines")
async def create_machine(data: MachineCreate):
    tenant_id = get_tenant_id()
    try:
        with get_db_session() as session:
            new_machine = MachineModel(
                tenant_id=tenant_id,
                name=data.name,
                status=data.status,
                room_id=data.room_id
            )
            session.add(new_machine)
            session.commit()
            session.refresh(new_machine)
            return {
                "message": "Machine created successfully",
                "machine_id": new_machine.id,
                "machine": machine_to_dict(new_machine)
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create machine: {str(e)}")

@router.put("/machines/{machine_id}")
async def update_machine(machine_id: int, data: MachineCreate):
    tenant_id = get_tenant_id()
    try:
        with get_db_session() as session:
            machine = session.query(MachineModel).filter(
                and_(MachineModel.id == machine_id, MachineModel.tenant_id == tenant_id)
            ).first()
            if not machine:
                raise HTTPException(status_code=404, detail="Machine not found")
            
            if data.name is not None: machine.name = data.name
            if data.status is not None: machine.status = data.status
            if data.room_id is not None: machine.room_id = data.room_id
            
            session.commit()
            session.refresh(machine)
            return {
                "message": "Machine updated successfully",
                "machine": machine_to_dict(machine)
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@router.delete("/machines/{machine_id}")
async def delete_machine(machine_id: int):
    tenant_id = get_tenant_id()
    try:
        with get_db_session() as session:
            machine = session.query(MachineModel).filter(
                and_(MachineModel.id == machine_id, MachineModel.tenant_id == tenant_id)
            ).first()
            if not machine:
                raise HTTPException(status_code=404, detail="Machine not found")
            session.delete(machine)
            session.commit()
            return {"message": f"Machine with ID {machine_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")