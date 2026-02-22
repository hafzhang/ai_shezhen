"""
API v1 router package.
"""

# Import and include endpoints
from api_service.app.api.v1 import endpoints

# Export the router from endpoints module
api_router = endpoints.api_router

__all__ = ["api_router"]
