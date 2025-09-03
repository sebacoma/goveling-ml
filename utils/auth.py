from typing import Optional
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from settings import settings

security = HTTPBearer(auto_error=False)

async def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Validar API key"""
    if not settings.API_KEY:
        # Si no hay API key configurada, permitir acceso
        return "public"
    
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="API key requerida"
        )
    
    if credentials.credentials != settings.API_KEY:
        raise HTTPException(
            status_code=401,
            detail="API key inválida"
        )
    
    return credentials.credentials

async def get_optional_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[str]:
    """Obtener API key opcional"""
    if credentials:
        return credentials.credentials
    return None
