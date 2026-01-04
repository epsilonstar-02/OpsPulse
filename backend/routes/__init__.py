"""
API Routes Package for the Dashboard Backend.
"""

from .analytics import router as analytics_router
from .system import router as system_router
from .logs import router as logs_router
from .websocket import router as websocket_router
