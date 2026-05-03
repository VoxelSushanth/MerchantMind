"""
API routes for authentication and OAuth.
"""
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.api.schemas import TokenResponse, RazorpayOAuthCallback, MerchantResponse
from app.core.database import get_db
from app.core.security import create_access_token, encrypt_token
from app.models import Merchant

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/razorpay")
async def razorpay_oauth_redirect(
    redirect_uri: str = Query(...),
):
    """
    Initiate Razorpay OAuth flow.
    
    Redirects merchant to Razorpay's authorization page.
    """
    from app.core.config import get_settings
    settings = get_settings()
    
    # Generate state parameter for CSRF protection
    import secrets
    state = secrets.token_urlsafe(32)
    
    # Razorpay OAuth URL
    auth_url = (
        "https://accounts.razorpay.com/authorize"
        f"?client_id={settings.RAZORPAY_KEY_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=read_write"
        f"&state={state}"
    )
    
    return {"authorization_url": auth_url, "state": state}


@router.post("/razorpay/callback", response_model=TokenResponse)
async def razorpay_oauth_callback(
    callback_data: RazorpayOAuthCallback,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle OAuth callback from Razorpay.
    
    Exchanges authorization code for access token and creates/updates merchant.
    """
    from app.core.config import get_settings
    settings = get_settings()
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://accounts.razorpay.com/oauth/token",
            data={
                "code": callback_data.code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.RAZORPAY_OAUTH_REDIRECT_URI,
            },
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
        )
        
        if token_response.status_code != 200:
            logger.error("Token exchange failed", status=token_response.status_code)
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="No access token received")
    
    # Fetch merchant profile from Razorpay
    import base64
    auth_header = f"Basic {base64.b64encode(f'{access_token}:'.encode()).decode()}"
    
    async with httpx.AsyncClient() as client:
        profile_response = await client.get(
            "https://api.razorpay.com/v1/account",
            headers={"Authorization": auth_header},
        )
        
        if profile_response.status_code != 200:
            logger.error("Profile fetch failed", status=profile_response.status_code)
            raise HTTPException(status_code=400, detail="Failed to fetch merchant profile")
        
        profile = profile_response.json()
    
    # Extract merchant info
    razorpay_merchant_id = profile.get("id")
    name = profile.get("name", "Unknown Merchant")
    email = profile.get("email", "unknown@example.com")
    
    # Encrypt the access token
    access_token_encrypted = encrypt_token(access_token)
    
    # Check if merchant exists
    result = await db.execute(
        select(Merchant).where(Merchant.razorpay_merchant_id == razorpay_merchant_id)
    )
    merchant = result.scalar_one_or_none()
    
    if merchant:
        # Update existing merchant
        merchant.access_token_encrypted = access_token_encrypted
        merchant.name = name
        merchant.email = email
    else:
        # Create new merchant
        merchant = Merchant(
            razorpay_merchant_id=razorpay_merchant_id,
            name=name,
            email=email,
            access_token_encrypted=access_token_encrypted,
        )
        db.add(merchant)
    
    await db.commit()
    await db.refresh(merchant)
    
    # Generate JWT for our app
    jwt_token = create_access_token(
        data={"sub": merchant.id, "merchant_id": merchant.id}
    )
    
    logger.info("Merchant authenticated", merchant_id=merchant.id)
    
    return TokenResponse(
        access_token=jwt_token,
        token_type="bearer",
        merchant_id=merchant.id,
    )


@router.get("/me", response_model=MerchantResponse)
async def get_current_merchant(
    db: AsyncSession = Depends(get_db),
    # In production, add JWT dependency here
    # merchant: Merchant = Depends(get_current_user)
):
    """
    Get current authenticated merchant info.
    
    For demo purposes, returns first merchant.
    Add proper JWT authentication in production.
    """
    result = await db.execute(select(Merchant).limit(1))
    merchant = result.scalar_one_or_none()
    
    if not merchant:
        raise HTTPException(status_code=404, detail="No merchant found")
    
    return MerchantResponse.model_validate(merchant)
