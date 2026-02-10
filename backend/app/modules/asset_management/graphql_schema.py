import strawberry
from typing import Optional, List
from sqlalchemy import and_
from app.core.db_utils import get_db_session
from app.modules.asset_management.models import RoomModel, MachineModel
from app.core.config import settings

# --- HELPERS ---
def get_tenant_id() -> str:
    """Gets the tenant ID from settings"""
    return settings.TENANT_ID

# --- STRAWBERRY TYPES ---
@strawberry.type
class RoomType:
    id: int
    room_number: Optional[str] = None
    room_type: Optional[str] = None
    is_available: bool

@strawberry.type
class MachineType:
    id: int
    name: Optional[str] = None
    status: Optional[str] = None
    room_id: Optional[int] = None

# --- GRAPHQL QUERIES (READ) ---

@strawberry.type
class Query:
    @strawberry.field
    async def get_rooms(self) -> List[RoomType]:
        """Fetches all rooms for the current tenant"""
        try:
            with get_db_session() as session:
                rooms = session.query(RoomModel).filter(
                    RoomModel.tenant_id == get_tenant_id()
                ).all()
                return rooms
        except Exception as e:
            raise Exception(f"Failed to fetch rooms: {str(e)}")

    @strawberry.field
    async def get_machines(self) -> List[MachineType]:
        """Fetches all machines for the current tenant"""
        try:
            with get_db_session() as session:
                machines = session.query(MachineModel).filter(
                    MachineModel.tenant_id == get_tenant_id()
                ).all()
                return machines
        except Exception as e:
            raise Exception(f"Failed to fetch machines: {str(e)}")

# --- GRAPHQL MUTATIONS (CREATE, UPDATE, DELETE) ---

@strawberry.type
class Mutation:
    
    # --- ROOM MUTATIONS ---
    @strawberry.mutation
    async def create_room(self, room_number: Optional[str] = None, room_type: Optional[str] = None) -> RoomType:
        """Creates a new procedure room"""
        tenant_id = get_tenant_id()
        try:
            with get_db_session() as session:
                new_room = RoomModel(
                    tenant_id=tenant_id,
                    room_number=room_number,
                    room_type=room_type,
                    is_available=True
                )
                session.add(new_room)
                session.commit()
                session.refresh(new_room)
                return new_room
        except Exception as e:
            raise Exception(f"Failed to create room: {str(e)}")

    @strawberry.mutation
    async def update_room(self, id: int, room_number: Optional[str] = None, room_type: Optional[str] = None) -> RoomType:
        """Updates an existing room's details"""
        tenant_id = get_tenant_id()
        try:
            with get_db_session() as session:
                room = session.query(RoomModel).filter(
                    and_(RoomModel.id == id, RoomModel.tenant_id == tenant_id)
                ).first()
                if not room:
                    raise Exception(f"Room with ID {id} not found")
                
                if room_number is not None: room.room_number = room_number
                if room_type is not None: room.room_type = room_type
                
                session.commit()
                session.refresh(room)
                return room
        except Exception as e:
            raise Exception(f"Failed to update room: {str(e)}")

    @strawberry.mutation
    async def delete_room(self, id: int) -> bool:
        """Deletes a room by ID"""
        tenant_id = get_tenant_id()
        try:
            with get_db_session() as session:
                room = session.query(RoomModel).filter(
                    and_(RoomModel.id == id, RoomModel.tenant_id == tenant_id)
                ).first()
                if not room:
                    return False
                session.delete(room)
                session.commit()
                return True
        except Exception as e:
            raise Exception(f"Failed to delete room: {str(e)}")

    # --- MACHINE MUTATIONS ---

    @strawberry.mutation
    async def create_machine(self, name: Optional[str] = None, status: Optional[str] = None, room_id: Optional[int] = None) -> MachineType:
        """Creates a new machine record"""
        tenant_id = get_tenant_id()
        try:
            with get_db_session() as session:
                new_machine = MachineModel(
                    tenant_id=tenant_id,
                    name=name,
                    status=status,
                    room_id=room_id
                )
                session.add(new_machine)
                session.commit()
                session.refresh(new_machine)
                return new_machine
        except Exception as e:
            raise Exception(f"Failed to create machine: {str(e)}")

    @strawberry.mutation
    async def update_machine(self, id: int, name: Optional[str] = None, status: Optional[str] = None, room_id: Optional[int] = None) -> MachineType:
        """Updates an existing machine's details"""
        tenant_id = get_tenant_id()
        try:
            with get_db_session() as session:
                machine = session.query(MachineModel).filter(
                    and_(MachineModel.id == id, MachineModel.tenant_id == tenant_id)
                ).first()
                if not machine:
                    raise Exception(f"Machine with ID {id} not found")
                
                if name is not None: machine.name = name
                if status is not None: machine.status = status
                if room_id is not None: machine.room_id = room_id
                
                session.commit()
                session.refresh(machine)
                return machine
        except Exception as e:
            raise Exception(f"Failed to update machine: {str(e)}")

    @strawberry.mutation
    async def delete_machine(self, id: int) -> bool:
        """Deletes a machine by ID"""
        tenant_id = get_tenant_id()
        try:
            with get_db_session() as session:
                machine = session.query(MachineModel).filter(
                    and_(MachineModel.id == id, MachineModel.tenant_id == tenant_id)
                ).first()
                if not machine:
                    return False
                session.delete(machine)
                session.commit()
                return True
        except Exception as e:
            raise Exception(f"Failed to delete machine: {str(e)}")