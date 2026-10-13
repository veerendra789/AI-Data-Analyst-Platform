from __future__ import annotations

from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from uuid import uuid4

from app.api.deps import get_current_user
from app.schemas.data_preparation import ApplyPreparationRequest, SavePreparationRequest
from app.schemas.datasets import DatasetResponse
from app.services.data_preparation_service import (
    PreparationError,
    analyze_csv,
    apply_plan,
    preview_frame,
    write_clean_csv,
)
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
    create_preparation,
    delete_preparation as remove_preparation,
    find_dataset_by_preparation,
    get_preparation as load_preparation,
    update_preparation,
)


router = APIRouter(prefix="/api/data-preparation", tags=["Data Preparation"])


class PreparationUploadInit(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    file_size: int = Field(gt=0)


class PreparationUploadComplete(BaseModel):
    preparation_id: str = Field(min_length=1, max_length=64)


class PreparationUploadCancel(BaseModel):
    preparation_id: str = Field(min_length=1, max_length=64)


def get_preparation(preparation_id: str, current_user: object) -> object:
    preparation = load_preparation(preparation_id, current_user.uid)
    if preparation is None:
        raise HTTPException(status_code=404, detail="Preparation session not found.")
    try:
        preparation.source_path = str(
            download_file(preparation.sourceStoragePath, current_user.uid, f"{preparation.id}-source")
        )
        if preparation.outputStoragePath:
            preparation.output_path = str(
                download_file(preparation.outputStoragePath, current_user.uid, f"{preparation.id}-cleaned")
            )
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="The source file for this preparation has expired.") from None
    return preparation


def _payload(preparation: object) -> dict:
    return {
        "id": preparation.id,
        "status": preparation.status,
        "filename": preparation.source_filename,
        "overview": preparation.metadata_json["overview"],
        "columns": preparation.metadata_json["columns"],
        "issues": preparation.metadata_json["issues"],
        "plan": preparation.plan_json,
        "comparison": preparation.metadata_json.get("comparison"),
        "history": preparation.history_json,
    }


@router.post("/upload/init", status_code=status.HTTP_201_CREATED)
def initialize_preparation_upload(
    request: PreparationUploadInit,
    current_user: object = Depends(get_current_user),
) -> dict[str, str]:
    filename = validate_filename(request.filename)[:255]
    validate_content_type(request.content_type)
    if request.file_size > settings.max_upload_size:
        raise HTTPException(status_code=413, detail="The uploaded file is too large.")
    preparation_id = uuid4().hex
    source_storage_path = object_path(current_user.uid, "structuringJobs", preparation_id, "source.csv")
    create_preparation(
        current_user.uid,
        {
            "sourceFilename": filename,
            "fileSize": request.file_size,
            "sourceStoragePath": source_storage_path,
            "outputStoragePath": None,
            "status": "UPLOADING",
            "metadata": {},
            "plan": [],
            "history": [],
        },
        preparation_id,
    )
    return {"preparation_id": preparation_id, "storage_path": source_storage_path}


@router.post("/upload/complete", status_code=status.HTTP_201_CREATED)
def complete_preparation_upload(
    request: PreparationUploadComplete,
    current_user: object = Depends(get_current_user),
) -> dict:
    preparation = load_preparation(request.preparation_id, current_user.uid)
    if preparation is None or preparation.status != "UPLOADING":
        raise HTTPException(status_code=404, detail="Pending preparation upload not found.")
    try:
        source_path = download_file(
            preparation.sourceStoragePath,
            current_user.uid,
            f"{preparation.id}-source",
        )
        actual_size = source_path.stat().st_size
        if actual_size != preparation.fileSize or actual_size > settings.max_upload_size:
            delete_file(preparation.sourceStoragePath)
            remove_preparation(preparation.id)
            if actual_size > settings.max_upload_size:
                raise HTTPException(status_code=413, detail="The uploaded file is too large.")
            raise HTTPException(status_code=400, detail="Uploaded file size did not match the upload request.")
        metadata, plan = analyze_csv(source_path, preparation.source_filename)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail="The uploaded file is not available in Supabase Storage.") from None
    except PreparationError as exc:
        delete_file(preparation.sourceStoragePath)
        remove_preparation(preparation.id)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    update_preparation(preparation.id, status="ANALYZED", metadata_json=metadata, plan_json=plan)
    preparation.status = "ANALYZED"
    preparation.metadata_json = metadata
    preparation.plan_json = plan
    preparation.source_path = str(source_path)
    return {**_payload(preparation), "preview": metadata["preview"]}


@router.post("/upload/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_preparation_upload(
    request: PreparationUploadCancel,
    current_user: object = Depends(get_current_user),
) -> Response:
    preparation = load_preparation(request.preparation_id, current_user.uid)
    if preparation is None or preparation.status != "UPLOADING":
        raise HTTPException(status_code=404, detail="Pending preparation upload not found.")
    try:
        delete_file(preparation.sourceStoragePath)
    except Exception:
        pass
    remove_preparation(preparation.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/analyze", status_code=status.HTTP_201_CREATED)
async def analyze_dataset(
    file: UploadFile = File(...),
    current_user: object = Depends(get_current_user),
) -> dict:
    path, _ = await store_upload(file)
    filename = Path((file.filename or "dataset.csv").replace("\\", "/")).name[:255]
    try:
        metadata, plan = analyze_csv(path, filename)
    except PreparationError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The CSV could not be analyzed.") from None
    preparation_id = uuid4().hex
    source_storage_path = object_path(current_user.uid, "structuringJobs", preparation_id, "source.csv")
    try:
        upload_file(path, source_storage_path)
        preparation = create_preparation(
            current_user.uid,
            {
                "sourceFilename": filename,
                "sourceStoragePath": source_storage_path,
                "outputStoragePath": None,
                "status": "ANALYZED",
                "metadata": metadata,
                "plan": plan,
                "history": [],
            },
            preparation_id,
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="The preparation session could not be saved.") from None
    path.unlink(missing_ok=True)
    preparation.source_path = str(download_file(source_storage_path, current_user.uid, f"{preparation.id}-source"))
    return {**_payload(preparation), "preview": metadata["preview"]}


@router.get("/{preparation_id}")
def read_preparation(
    preparation_id: str,
    current_user: object = Depends(get_current_user),
) -> dict:
    return _payload(get_preparation(preparation_id, current_user))


@router.get("/{preparation_id}/preview")
def preview_preparation(
    preparation_id: str,
    version: str = "original",
    limit: int = 50,
    current_user: object = Depends(get_current_user),
) -> dict:
    preparation = get_preparation(preparation_id, current_user)
    bounded_limit = min(max(limit, 1), 100)
    if version == "original":
        metadata = preparation.metadata_json["preview"]
        return {**metadata, "rows": metadata["rows"][:bounded_limit]}
    if version != "cleaned" or not preparation.output_path or not Path(preparation.output_path).is_file():
        raise HTTPException(status_code=409, detail="A cleaned preview is not available yet.")
    import pandas as pd

    try:
        frame = pd.read_csv(preparation.output_path, nrows=bounded_limit)
        return {**preview_frame(frame, bounded_limit), "total_rows": preparation.metadata_json["comparison"]["final_row_count"]}
    except Exception:
        raise HTTPException(status_code=500, detail="The cleaned preview could not be read.") from None


@router.post("/{preparation_id}/preview")
def preview_proposed_changes(
    preparation_id: str,
    request: ApplyPreparationRequest,
    current_user: object = Depends(get_current_user),
) -> dict:
    preparation = get_preparation(preparation_id, current_user)
    try:
        frame, comparison, _ = apply_plan(
            Path(preparation.source_path),
            preparation.metadata_json,
            preparation.plan_json,
            request.model_dump(),
        )
        return {"preview": preview_frame(frame), "comparison": comparison, "status": "PROPOSED"}
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="The source file for this preparation has expired.") from None
    except Exception:
        raise HTTPException(status_code=400, detail="The proposed transformations could not be previewed.") from None


@router.post("/{preparation_id}/apply")
def apply_preparation(
    preparation_id: str,
    request: ApplyPreparationRequest,
    current_user: object = Depends(get_current_user),
) -> dict:
    preparation = get_preparation(preparation_id, current_user)
    existing_dataset = find_dataset_by_preparation(current_user.uid, preparation.id)
    if existing_dataset is not None:
        raise HTTPException(status_code=409, detail="This preparation has already been saved. Start a new preparation to revise it.")
    try:
        frame, comparison, history = apply_plan(
            Path(preparation.source_path),
            preparation.metadata_json,
            preparation.plan_json,
            request.model_dump(),
        )
        output_path = Path(gettempdir()) / "ai-data-analyst" / "prepared" / f"{preparation.id}.csv"
        write_clean_csv(frame, output_path)
    except PreparationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="The source file for this preparation has expired.") from None
    except Exception:
        raise HTTPException(status_code=400, detail="The selected transformations could not be applied.") from None
    output_storage_path = object_path(current_user.uid, "structuringJobs", preparation.id, "cleaned.csv")
    try:
        upload_file(output_path, output_storage_path)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="The cleaned dataset could not be stored.") from None
    update_preparation(
        preparation.id,
        outputStoragePath=output_storage_path,
        status="APPLIED",
        metadata_json={**preparation.metadata_json, "comparison": comparison},
        history_json=preparation.history_json + history,
    )
    preparation.output_path = str(output_path)
    preparation.status = "APPLIED"
    preparation.metadata_json = {**preparation.metadata_json, "comparison": comparison}
    preparation.history_json = preparation.history_json + history
    return {**_payload(preparation), "preview": preview_frame(frame)}


@router.post("/{preparation_id}/save", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def save_preparation(
    preparation_id: str,
    request: SavePreparationRequest,
    current_user: object = Depends(get_current_user),
) -> object:
    preparation = get_preparation(preparation_id, current_user)
    if preparation.status != "APPLIED" or not preparation.output_path or not Path(preparation.output_path).is_file():
        raise HTTPException(status_code=409, detail="Apply transformations before saving the prepared dataset.")
    try:
        with Path(preparation.output_path).open("rb") as source:
            parsed = parse_csv(source)
    except (CsvValidationError, OSError):
        raise HTTPException(status_code=400, detail="The prepared CSV failed dataset validation.") from None
    existing = find_dataset_by_preparation(current_user.uid, preparation.id)
    if existing is not None:
        return existing
    original_name = f"{Path(preparation.source_filename).stem}_cleaned.csv"[:255]
    dataset_id = uuid4().hex
    storage_path = object_path(current_user.uid, "datasets", dataset_id, original_name)
    local_output_path = Path(preparation.output_path)
    upload_file(local_output_path, storage_path)
    dataset = create_dataset(
        current_user.uid,
        {
            "name": (request.name or Path(original_name).stem)[:255],
            "originalFilename": original_name,
            "storagePath": storage_path,
            "rowCount": parsed.row_count,
            "columnCount": len(parsed.headers),
            "fileSize": local_output_path.stat().st_size,
            "status": "COMPLETED",
            "sourcePreparationId": preparation.id,
            "columns": parsed.column_stats,
        },
        dataset_id,
    )
    dataset.file_path = str(local_output_path)
    return dataset


@router.get("/{preparation_id}/download")
def download_preparation(
    preparation_id: str,
    current_user: object = Depends(get_current_user),
) -> FileResponse:
    preparation = get_preparation(preparation_id, current_user)
    if not preparation.output_path or not Path(preparation.output_path).is_file():
        raise HTTPException(status_code=409, detail="Apply transformations before downloading the CSV.")
    filename = f"{Path(preparation.source_filename).stem}_cleaned.csv"
    return FileResponse(preparation.output_path, media_type="text/csv", filename=filename)


@router.delete("/{preparation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preparation(
    preparation_id: str,
    current_user: object = Depends(get_current_user),
) -> Response:
    preparation = get_preparation(preparation_id, current_user)
    existing_dataset = find_dataset_by_preparation(current_user.uid, preparation.id)
    delete_file(preparation.sourceStoragePath)
    if preparation.outputStoragePath and existing_dataset is None:
        delete_file(preparation.outputStoragePath)
    remove_preparation(preparation.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)