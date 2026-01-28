"""
Unit tests for database utility functions
"""
import pytest
from unittest.mock import MagicMock, patch
from app.core.db_utils import get_db_session, require_db_session
from app.core.db_session import SessionLocal


class TestGetDbSession:
    """Tests for get_db_session context manager"""
    
    def test_get_db_session_commits_on_success(self):
        """Test that session commits on successful operation"""
        with patch('app.core.db_utils.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            
            with get_db_session() as session:
                assert session == mock_session
            
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.rollback.assert_not_called()
    
    def test_get_db_session_rolls_back_on_exception(self):
        """Test that session rolls back on exception"""
        with patch('app.core.db_utils.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            
            with pytest.raises(ValueError):
                with get_db_session() as session:
                    raise ValueError("Test error")
            
            mock_session.rollback.assert_called_once()
            mock_session.close.assert_called_once()
            mock_session.commit.assert_not_called()
    
    def test_get_db_session_closes_on_exit(self):
        """Test that session is always closed"""
        with patch('app.core.db_utils.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            
            with get_db_session() as session:
                pass
            
            mock_session.close.assert_called_once()


class TestRequireDbSession:
    """Tests for require_db_session function"""
    
    def test_require_db_session_creates_session(self):
        """Test that require_db_session creates a new session"""
        with patch('app.core.db_utils.SessionLocal') as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            
            session = require_db_session()
            
            assert session == mock_session
            mock_session_local.assert_called_once()
    
    def test_require_db_session_raises_on_error(self):
        """Test that require_db_session raises error if session creation fails"""
        with patch('app.core.db_utils.SessionLocal', side_effect=Exception("DB Error")):
            with pytest.raises(RuntimeError, match="Database session not available"):
                require_db_session()

