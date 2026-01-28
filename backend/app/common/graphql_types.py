"""Shared GraphQL types used across multiple modules"""
import strawberry

@strawberry.type
class PaginationInfo:
    """Pagination information"""
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool

