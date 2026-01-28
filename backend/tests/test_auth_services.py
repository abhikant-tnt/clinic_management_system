"""
Unit tests for authentication services
"""
import pytest
import bcrypt
from app.modules.auth.services import (
    hash_password,
    verify_password,
    create_access_token
)


class TestHashPassword:
    """Tests for hash_password function"""
    
    def test_hash_password_success(self):
        """Test successful password hashing"""
        password = "testpassword123"
        hashed = hash_password(password)
        
        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert len(hashed) > 0
    
    def test_hash_password_different_hashes(self):
        """Test that same password produces different hashes (due to salt)"""
        password = "testpassword123"
        hashed1 = hash_password(password)
        hashed2 = hash_password(password)
        
        # Hashes should be different due to random salt
        assert hashed1 != hashed2
    
    def test_hash_password_too_long(self):
        """Test that password exceeding 72 bytes raises ValueError"""
        # Create a password longer than 72 bytes
        long_password = "a" * 73
        
        with pytest.raises(ValueError, match="exceeds maximum length"):
            hash_password(long_password)
    
    def test_hash_password_exactly_72_bytes(self):
        """Test that password of exactly 72 bytes works"""
        password = "a" * 72
        hashed = hash_password(password)
        
        assert hashed is not None
        assert isinstance(hashed, str)


class TestVerifyPassword:
    """Tests for verify_password function"""
    
    def test_verify_password_correct(self):
        """Test verification of correct password"""
        password = "testpassword123"
        hashed = hash_password(password)
        
        result = verify_password(password, hashed)
        assert result is True
    
    def test_verify_password_incorrect(self):
        """Test verification of incorrect password"""
        password = "testpassword123"
        hashed = hash_password(password)
        
        result = verify_password("wrongpassword", hashed)
        assert result is False
    
    def test_verify_password_too_long(self):
        """Test that password exceeding 72 bytes raises ValueError"""
        password = "testpassword123"
        hashed = hash_password(password)
        long_password = "a" * 73
        
        with pytest.raises(ValueError, match="exceeds maximum length"):
            verify_password(long_password, hashed)
    
    def test_verify_password_different_hashes(self):
        """Test that different hashes of same password both verify correctly"""
        password = "testpassword123"
        hashed1 = hash_password(password)
        hashed2 = hash_password(password)
        
        # Both hashes should verify the same password
        assert verify_password(password, hashed1) is True
        assert verify_password(password, hashed2) is True


class TestCreateAccessToken:
    """Tests for create_access_token function"""
    
    def test_create_access_token_basic(self):
        """Test creating access token with basic data"""
        data = {"sub": "testuser", "user_type": "admin"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_create_access_token_with_expires_delta(self):
        """Test creating access token with custom expiration"""
        from datetime import timedelta
        
        data = {"sub": "testuser"}
        expires_delta = timedelta(hours=2)
        token = create_access_token(data, expires_delta)
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_create_access_token_contains_data(self):
        """Test that token contains the encoded data"""
        import jwt
        from app.core.config import settings
        
        data = {"sub": "testuser", "user_type": "admin"}
        token = create_access_token(data)
        
        # Decode token to verify it contains the data
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        assert decoded["sub"] == "testuser"
        assert decoded["user_type"] == "admin"

