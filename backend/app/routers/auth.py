from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserResponse, UserProfileUpdate
from app.dependencies.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, db: Annotated[Session, Depends(get_db)]):
    """Register a new user. Returns a JWT on success."""
    # Check email uniqueness
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    """Authenticate user and return JWT."""
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    """Return the currently authenticated user's profile."""
    return current_user


@router.put("/profile", response_model=UserResponse)
def update_profile(
    body: UserProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Update authenticated user's profile details."""
    if body.name is not None:
        current_user.name = body.name.strip()
    if body.company_name is not None:
        current_user.company_name = body.company_name.strip()
    if body.company_url is not None:
        clean_company_url = body.company_url.strip()
        if clean_company_url and not clean_company_url.startswith(("http://", "https://")):
            clean_company_url = "https://" + clean_company_url
        current_user.company_url = clean_company_url if clean_company_url else None
    if body.company_description is not None:
        current_user.company_description = body.company_description.strip()
    if body.slack_webhook_url is not None:
        current_user.slack_webhook_url = body.slack_webhook_url.strip()
    if body.is_onboarded is not None:
        current_user.is_onboarded = body.is_onboarded

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/onboard", response_model=UserResponse)
async def complete_onboarding(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    method: str = Form("text"),
    company_name: Optional[str] = Form(None),
    company_url: Optional[str] = Form(None),
    description_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
):
    """
    Gather user company details via text description, URL scraping, or uploaded document,
    extract intelligence, save to profile, and set is_onboarded = True.
    """
    collected_details = []

    if company_name and company_name.strip():
        current_user.company_name = company_name.strip()

    # 1. URL Method: Scrape company website if URL provided
    target_url = company_url.strip() if company_url and company_url.strip() else None
    if target_url:
        if not target_url.startswith(("http://", "https://")):
            target_url = "https://" + target_url
        current_user.company_url = target_url
        try:
            from app.services.scraper import scrape_url
            scrape_res = scrape_url(target_url)
            if scrape_res.get("clean_text"):
                collected_details.append(f"Company Website Content ({target_url}):\n" + scrape_res["clean_text"][:3000])
        except Exception as e:
            print(f"[Onboarding] Scrape URL error: {e}")

    # 2. Text Method: User-provided text description
    if description_text and description_text.strip():
        collected_details.append("User Description:\n" + description_text.strip())

    # 3. Document Method: File upload (PDF, TXT, MD, etc.)
    if file:
        try:
            content = await file.read()
            filename = file.filename.lower()
            extracted_text = ""
            if filename.endswith(".pdf"):
                try:
                    import pypdf
                    import io
                    reader = pypdf.PdfReader(io.BytesIO(content))
                    extracted_text = "\n".join([page.extract_text() or "" for page in reader.pages])
                except Exception:
                    extracted_text = content.decode("utf-8", errors="ignore")
            else:
                extracted_text = content.decode("utf-8", errors="ignore")

            if extracted_text.strip():
                collected_details.append(f"Uploaded Document ({file.filename}):\n" + extracted_text.strip()[:4000])
        except Exception as e:
            print(f"[Onboarding] File read error: {e}")

    # Process and summarize collected details using LLM or structured formatting
    raw_combined = "\n\n".join(collected_details)
    if raw_combined:
        try:
            from app.services.llm import call_openrouter
            from app.config import settings
            if settings.LLM_API_KEY:
                prompt = (
                    f"Summarize the following company information for company '{current_user.company_name or 'User Company'}'. "
                    "Provide a clean, executive synthesis of their product, value proposition, pricing model, and target customers:\n\n"
                    f"{raw_combined[:4000]}"
                )
                summary, _ = call_openrouter(prompt, settings.LLM_API_KEY)
                current_user.company_description = summary.strip()
            else:
                current_user.company_description = raw_combined[:2000]
        except Exception as e:
            print(f"[Onboarding] LLM summary warning: {e}")
            current_user.company_description = raw_combined[:2000]

    current_user.is_onboarded = True
    db.commit()
    db.refresh(current_user)
    return current_user


