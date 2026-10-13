from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.schemas.datasets import DatasetListResponse, DatasetPreviewResponse, DatasetResponse
from app.services.dataset_service import (
    CsvValidationError,
    parse_csv,
    settings,
    store_upload,
    validate_content_type,
    validate_filename,
)
from app.services.supabase_storage import delete_file, download_file, object_path, upload_file
from app.services.supabase_repository import (
    create_dataset,
    delete_dataset as remove_dataset,
    get_dataset,
    list_datasets as load_datasets,
    update_dataset,
)


router = APIRouter(prefix="/api/datasets", tags=["Datasets"])


class DatasetUploadInit(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    file_size: int = Field(gt=0)


class DatasetUploadComplete(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=64)


class DatasetUploadCancel(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=64)


def get_accessible_dataset(dataset_id: str, current_user: object) -> object:
    dataset = get_dataset(dataset_id, current_user.uid, allow_admin=current_user.role == "ADMIN")
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    try:
        dataset.file_path = str(download_file(dataset.storagePath, dataset.ownerId, dataset.id))
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="The stored dataset file is unavailable.") from None
    return dataset


@router.post("/upload/init", status_code=status.HTTP_201_CREATED)
def initialize_dataset_upload(
    request: DatasetUploadInit,
    current_user: object = Depends(get_current_user),
) -> dict[str, str]:
    filename = validate_filename(request.filename)
    validate_content_type(request.content_type)
    if request.file_size > settings.max_upload_size:
        raise HTTPException(status_code=413, detail="The uploaded file is too large.")
    dataset_id = uuid4().hex
    storage_path = object_path(current_user.uid, "datasets", dataset_id, filename)
    create_dataset(
        current_user.uid,
        {
            "name": Path(filename).stem[:255],
            "originalFilename": filename,
            "storagePath": storage_path,
            "fileSize": request.file_size,
            "rowCount": 0,
            "columnCount": 0,
            "status": "UPLOADING",
            "columns": [],
        },
        dataset_id,
    )
    return {"dataset_id": dataset_id, "storage_path": storage_path}


@router.post("/upload/complete", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def complete_dataset_upload(
    request: DatasetUploadComplete,
    current_user: object = Depends(get_current_user),
) -> object:
    dataset = get_dataset(request.dataset_id, current_user.uid)
    if dataset is None or dataset.status != "UPLOADING":
        raise HTTPException(status_code=404, detail="Pending dataset upload not found.")
    try:
        local_path = download_file(dataset.storagePath, current_user.uid, dataset.id)
        actual_size = local_path.stat().st_size
        if actual_size != dataset.file_size or actual_size > settings.max_upload_size:
            delete_file(dataset.storagePath)
            remove_dataset(dataset.id)
            if actual_size > settings.max_upload_size:
                raise HTTPException(status_code=413, detail="The uploaded file is too large.")
            raise HTTPException(status_code=400, detail="Uploaded file size did not match the upload request.")
        with local_path.open("rb") as input_file:
            parsed = parse_csv(input_file)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="The uploaded file is not available in Supabase Storage.") from None
    except CsvValidationError as exc:
        delete_file(dataset.storagePath)
        remove_dataset(dataset.id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    update_dataset(
        dataset.id,
        current_user.uid,
        row_count=parsed.row_count,
        column_count=len(parsed.headers),
        status="COMPLETED",
        columns=parsed.column_stats,
    )
    dataset = get_dataset(dataset.id, current_user.uid)
    dataset.file_path = str(local_path)
    return dataset


@router.post("/upload/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_dataset_upload(
    request: DatasetUploadCancel,
    current_user: object = Depends(get_current_user),
) -> Response:
    dataset = get_dataset(request.dataset_id, current_user.uid)
    if dataset is None or dataset.status != "UPLOADING":
        raise HTTPException(status_code=404, detail="Pending dataset upload not found.")
    try:
        delete_file(dataset.storagePath)
    except Exception:
        pass
    remove_dataset(dataset.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/upload", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: object = Depends(get_current_user),
) -> object:
    path, file_size = await store_upload(file)
    try:
        with path.open("rb") as input_file:
            parsed = parse_csv(input_file)
    except CsvValidationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_filename = Path((file.filename or "dataset.csv").replace("\\", "/")).name
    dataset_id = uuid4().hex
    storage_path = object_path(current_user.uid, "datasets", dataset_id, safe_filename)
    try:
        upload_file(path, storage_path)
        dataset = create_dataset(
            current_user.uid,
            {
                "name": Path(safe_filename).stem[:255],
                "originalFilename": safe_filename[:255],
                "storagePath": storage_path,
                "fileSize": file_size,
                "rowCount": parsed.row_count,
                "columnCount": len(parsed.headers),
                "status": "COMPLETED",
                "columns": parsed.column_stats,
            },
            dataset_id,
        )
    except Exception:
        try:
            delete_file(storage_path)
        except Exception:
            pass
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="The dataset could not be saved.") from None
    path.unlink(missing_ok=True)
    dataset.file_path = str(download_file(storage_path, current_user.uid, dataset.id))
    return dataset


@router.get("", response_model=DatasetListResponse)
def list_datasets(
    offset: int = 0,
    limit: int = 20,
    current_user: object = Depends(get_current_user),
) -> DatasetListResponse:
    bounded_limit = min(max(limit, 1), 100)
    items, total = load_datasets(current_user.uid, max(offset, 0), bounded_limit)
    return DatasetListResponse(items=items, total=total)


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset_route(
    dataset_id: str,
    current_user: object = Depends(get_current_user),
) -> object:
    return get_accessible_dataset(dataset_id, current_user)


@router.get("/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(
    dataset_id: str,
    current_user: object = Depends(get_current_user),
) -> DatasetPreviewResponse:
    dataset = get_accessible_dataset(dataset_id, current_user)
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
    dataset_id: str,
    current_user: object = Depends(get_current_user),
) -> None:
    dataset = get_accessible_dataset(dataset_id, current_user)
    delete_file(dataset.storagePath)
    remove_dataset(dataset.id)
