from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Dataset, DatasetColumn, DatasetStatus, User
from app.schemas.datasets import DatasetListResponse, DatasetPreviewResponse, DatasetResponse
from app.services.dataset_service import CsvValidationError, parse_csv, settings, store_upload


router = APIRouter(prefix="/api/datasets", tags=["Datasets"])


def get_accessible_dataset(dataset_id: int, current_user: User, db: Session) -> Dataset:
    query = select(Dataset).options(selectinload(Dataset.columns)).where(Dataset.id == dataset_id)
    if current_user.role != "ADMIN":
        query = query.where(Dataset.user_id == current_user.id)
    dataset = db.scalar(query)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset


@router.post("/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dataset:
    path, file_size = await store_upload(file)
    try:
        with path.open("rb") as input_file:
            parsed = parse_csv(input_file)
    except CsvValidationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_filename = Path((file.filename or "dataset.csv").replace("\\", "/")).name
    dataset = Dataset(
        user_id=current_user.id,
        name=Path(safe_filename).stem[:255],
        original_filename=safe_filename[:255],
        file_path=str(path),
        row_count=parsed.row_count,
        column_count=len(parsed.headers),
        file_size=file_size,
        status=DatasetStatus.COMPLETED,
        columns=[DatasetColumn(**column) for column in parsed.column_stats],
    )
    db.add(dataset)
    try:
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="The dataset could not be saved.") from None
    db.refresh(dataset)
    return get_accessible_dataset(dataset.id, current_user, db)


@router.get("", response_model=DatasetListResponse)
def list_datasets(
    offset: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetListResponse:
    bounded_limit = min(max(limit, 1), 100)
    query = select(Dataset).options(selectinload(Dataset.columns)).order_by(Dataset.created_at.desc()).offset(max(offset, 0)).limit(bounded_limit)
    count_query = select(func.count()).select_from(Dataset)
    if current_user.role != "ADMIN":
        query = query.where(Dataset.user_id == current_user.id)
        count_query = count_query.where(Dataset.user_id == current_user.id)
    return DatasetListResponse(items=list(db.scalars(query).all()), total=db.scalar(count_query) or 0)


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dataset:
    return get_accessible_dataset(dataset_id, current_user, db)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetPreviewResponse:
    dataset = get_accessible_dataset(dataset_id, current_user, db)
    try:
        with Path(dataset.file_path).open("rb") as input_file:
            parsed = parse_csv(input_file)
    except (FileNotFoundError, CsvValidationError) as exc:
        raise HTTPException(status_code=500, detail="The stored dataset could not be read.") from exc
    rows = [dict(zip(parsed.headers, row)) for row in parsed.rows]
    return DatasetPreviewResponse(
        dataset_id=dataset.id,
        columns=parsed.headers,
        rows=rows,
        total_rows=parsed.row_count,
        returned_rows=len(rows),
    )


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(
    dataset_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    dataset = get_accessible_dataset(dataset_id, current_user, db)
    Path(dataset.file_path).unlink(missing_ok=True)
    db.delete(dataset)
    db.commit()
