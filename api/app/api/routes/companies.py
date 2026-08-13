from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.company import Company
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter()


def _clean_cnpj(cnpj: str) -> str:
    """Remove formatação do CNPJ."""
    return cnpj.replace('.', '').replace('-', '').replace('/', '').strip()


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    raw_cnpj = _clean_cnpj(company_data.cnpj)

    stmt = select(Company).where(Company.cnpj == raw_cnpj)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company with this CNPJ already exists",
        )

    company = Company(
        legal_name=company_data.legal_name,
        trade_name=company_data.trade_name,
        cnpj=raw_cnpj,
        rh_name=company_data.rh_name,
        rh_email=str(company_data.rh_email) if company_data.rh_email else None,
        rh_phone=company_data.rh_phone,
        address=company_data.address,
        city=company_data.city,
        state=company_data.state,
        zip_code=company_data.zip_code,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


@router.get("/", response_model=list[CompanyResponse])
async def list_companies(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    skip: int = 0,
    limit: int = 100,
):
    stmt = select(Company).offset(skip).limit(limit)
    result = await db.execute(stmt)
    companies = result.scalars().all()
    return companies


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    return company


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    company_data: CompanyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    update_data = company_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "cnpj" and value:
            value = _clean_cnpj(value)
        if field == "rh_email" and value:
            value = str(value)
        setattr(company, field, value)

    await db.commit()
    await db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    await db.delete(company)
    await db.commit()
