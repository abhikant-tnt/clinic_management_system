"""Database helper functions to reduce code duplication"""
from typing import Any, Optional, List, Dict
from sqlalchemy import and_
from app.core.db_utils import get_db_session


def check_exists(
    model_class: Any,
    table_name: str,
    id_field: str,
    entity_id: int,
    tenant_id: str
) -> bool:
    """
    Check if an entity exists in the database using ORM.
    
    Args:
        model_class: SQLAlchemy model class
        table_name: Database table name (deprecated, kept for compatibility)
        id_field: ID field name (usually 'id')
        entity_id: Entity ID to check
        tenant_id: Tenant ID
    
    Returns:
        True if entity exists, False otherwise
    """
    try:
        with get_db_session() as session:
            return session.query(model_class).filter(
                and_(
                    getattr(model_class, id_field) == entity_id,
                    model_class.tenant_id == tenant_id
                )
            ).first() is not None
    except Exception:
        return False


def get_by_id(
    model_class: Any,
    table_name: str,
    id_field: str,
    entity_id: int,
    tenant_id: str,
    columns: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Get an entity by ID from the database using ORM.
    
    Args:
        model_class: SQLAlchemy model class
        table_name: Database table name (deprecated, kept for compatibility)
        id_field: ID field name (usually 'id')
        entity_id: Entity ID to get
        tenant_id: Tenant ID
        columns: Deprecated, kept for backward compatibility
    
    Returns:
        Entity as dict or None if not found
    """
    try:
        with get_db_session() as session:
            entity = session.query(model_class).filter(
                and_(
                    getattr(model_class, id_field) == entity_id,
                    model_class.tenant_id == tenant_id
                )
            ).first()
            if entity:
                return {k: v for k, v in entity.__dict__.items() if not k.startswith('_')}
        return None
    except Exception:
        return None


def query_all(
    model_class: Any,
    table_name: str,
    tenant_id: str,
    filters: Optional[Dict[str, Any]] = None,
    columns: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Query all entities matching filters using ORM.
    
    Args:
        model_class: SQLAlchemy model class
        table_name: Database table name (deprecated, kept for compatibility)
        tenant_id: Tenant ID
        filters: Optional dict of field: value filters
        columns: Deprecated, kept for backward compatibility
    
    Returns:
        List of entities as dicts
    """
    try:
        with get_db_session() as session:
            query = session.query(model_class).filter(model_class.tenant_id == tenant_id)
            if filters:
                for field, value in filters.items():
                    query = query.filter(getattr(model_class, field) == value)
            entities = query.all()
            result = []
            for entity in entities:
                if hasattr(entity, '__dict__'):
                    result.append({k: v for k, v in entity.__dict__.items() if not k.startswith('_')})
            return result
    except Exception:
        return []

