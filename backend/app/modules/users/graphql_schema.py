"""GraphQL schema for Users module (Strawberry)"""
import strawberry
from typing import Optional, List
from app.common.graphql_types import PaginationInfo

@strawberry.type
class UserType:
    """GraphQL User type"""
    id: Optional[int] = None
    tenant_id: Optional[str] = None
    firstname: str
    lastname: str
    speciality: Optional[str] = None
    phone: str
    user_type: Optional[str] = None
    is_active: Optional[bool] = None

@strawberry.input
class UserInput:
    """GraphQL User input for creating"""
    firstname: str
    lastname: str
    speciality: Optional[str] = None
    phone: str
    user_type: Optional[str] = None

@strawberry.input
class UserUpdateInput:
    """GraphQL User input for updating"""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    speciality: Optional[str] = None
    phone: Optional[str] = None
    user_type: Optional[str] = None

@strawberry.type
class UserResponse:
    """Response type for paginated users"""
    users: List[UserType]
    pagination: PaginationInfo

@strawberry.type
class Query:
    """GraphQL Query type for Users"""
    
    @strawberry.field
    async def userMember(self, user_id: int) -> Optional[UserType]:
        """Get a single user by ID"""
        from app.modules.users.routes import get_user
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            user_data = await get_user(user_id, {})  # Pass empty dict for current_user
            if user_data:
                return UserType(**user_data)
            return None
        except HTTPException:
            return None
    
    @strawberry.field
    async def users(
        self,
        page: int = 1,
        limit: int = 10
    ) -> UserResponse:
        """Get all users"""
        from app.modules.users.routes import get_users
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await get_users(
                page=page,
                limit=limit,
                current_user={}
            )
            users_list = []
            for u in result.get("users", []):
                users_list.append(UserType(**u))
            
            pagination_data = result.get("pagination", {})
            pagination = PaginationInfo(
                total=pagination_data.get("total", 0),
                page=pagination_data.get("page", 1),
                limit=pagination_data.get("limit", 10),
                total_pages=pagination_data.get("total_pages", 1),
                has_next=pagination_data.get("has_next", False),
                has_prev=pagination_data.get("has_prev", False)
            )
            
            return UserResponse(users=users_list, pagination=pagination)
        except HTTPException:
            return UserResponse(users=[], pagination=PaginationInfo(total=0, page=1, limit=10, total_pages=1, has_next=False, has_prev=False))

@strawberry.type
class Mutation:
    """GraphQL Mutation type for Users"""
    
    @strawberry.mutation
    async def createUser(self, user: UserInput) -> UserType:
        """Create a new user"""
        from app.modules.users.routes import create_user, get_user
        from app.modules.users.schemas import UserCreate
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        user_data = UserCreate(
            firstname=user.firstname,
            lastname=user.lastname,
            speciality=user.speciality,
            phone=user.phone,
            user_type=user.user_type
        )
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            result = await create_user(user_data, {})  # Pass empty dict for current_user
            # Route returns {"message": "...", "user_id": ...}
            user_id = result.get("user_id")
            if not user_id:
                raise ValueError("User created but could not retrieve ID from response")
            
            # Fetch the created user
            user_data_result = await get_user(user_id, {})
            if user_data_result:
                return UserType(**user_data_result)
            raise ValueError("User created but could not retrieve from response")
        except HTTPException as e:
            raise ValueError(f"Failed to create user: {e.detail}") from e
    
    @strawberry.mutation
    async def updateUser(
        self,
        user_id: int,
        user: UserUpdateInput
    ) -> Optional[UserType]:
        """Update an existing user"""
        from app.modules.users.routes import update_user, get_user
        from app.modules.users.schemas import UserUpdate
        from fastapi import HTTPException
        
        # Convert GraphQL input to Pydantic model
        user_data = UserUpdate(
            firstname=user.firstname,
            lastname=user.lastname,
            speciality=user.speciality,
            phone=user.phone,
            user_type=user.user_type
        )
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            await update_user(user_id, user_data, {})  # Pass empty dict for current_user
            # Fetch the updated user
            user_result = await get_user(user_id, {})
            if user_result:
                return UserType(**user_result)
            return None
        except HTTPException as e:
            raise ValueError(f"Failed to update user: {e.detail}") from e
    
    @strawberry.mutation
    async def deleteUser(self, user_id: int) -> bool:
        """Delete a user by ID"""
        from app.modules.users.routes import delete_user
        from fastapi import HTTPException
        
        try:
            # Note: GraphQL calls route directly, auth should be handled via GraphQL context
            await delete_user(user_id, {})  # Pass empty dict for current_user
            return True
        except HTTPException:
            return False

# Create the GraphQL schema
schema = strawberry.Schema(query=Query, mutation=Mutation)
