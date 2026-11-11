"""receiver-app: upload files and folders to S3 under three data types."""
import logging
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, FastAPI, File, UploadFile
from fastapi.responses import FileResponse

from . import s3
from .auth import require_user
from .config import settings

log = logging.getLogger("receiver-app")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    s3.ensure_bucket()
    yield


app = FastAPI(title="receiver-app", lifespan=lifespan)


# --------------------------------------------------------------------------- helpers

def clean_relpath(name: str | None) -> str:
    """Normalise a client-supplied relative path; drop '..', '.', empty and drive parts."""
    if not name:
        return ""
    parts = name.replace("\\", "/").split("/")
    safe = [p for p in parts if p not in ("", ".", "..") and not p.endswith(":")]
    return "/".join(safe)


def make_key(type_prefix: str, relpath: str) -> str:
    return f"{settings.s3_root_prefix}{type_prefix}/{relpath}"


def _result() -> dict:
    return {"uploaded": [], "rejected": []}


def _reject(result: dict, name: str | None, reason: str) -> None:
    result["rejected"].append({"file": name or "<unnamed>", "reason": reason})


def _put(result: dict, fileobj, key: str, name: str) -> bool:
    try:
        s3.upload_fileobj(fileobj, key)
    except (ClientError, BotoCoreError) as exc:
        log.exception("S3 upload failed for %s", key)
        _reject(result, name, f"S3 error: {exc}")
        return False
    result["uploaded"].append(key)
    return True


# --------------------------------------------------------------------------- public routes

@app.get("/healthz", include_in_schema=False)
def healthz() -> dict:
    return {"status": "ok"}


# --------------------------------------------------------------------------- protected routes

router = APIRouter(dependencies=[Depends(require_user)])


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.post("/upload/zip")
def upload_zip(files: list[UploadFile] = File(...)) -> dict:
    """Store each .zip and also extract its contents to upload/zip/<zipname>/..."""
    result = _result()
    for f in files:
        rel = clean_relpath(f.filename)
        if not rel.lower().endswith(".zip"):
            _reject(result, f.filename, "not a .zip file")
            continue

        # Validate before writing anything.
        try:
            zf = zipfile.ZipFile(f.file)
        except zipfile.BadZipFile:
            _reject(result, f.filename, "invalid zip archive")
            continue
        with zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            total = sum(m.file_size for m in members)
            if total > settings.max_unzipped_bytes:
                _reject(
                    result, f.filename,
                    f"uncompressed size {total} exceeds limit {settings.max_unzipped_bytes}",
                )
                continue

            # 1) its contents, under a folder named after the zip
            base = rel[: -len(".zip")]
            for m in members:
                member_rel = clean_relpath(m.filename)
                if not member_rel:
                    continue
                try:
                    with zf.open(m) as src:
                        _put(result, src, make_key("zip", f"{base}/{member_rel}"),
                             f"{rel}:{m.filename}")
                except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
                    # e.g. encrypted members or unsupported compression
                    _reject(result, f"{rel}:{m.filename}", f"cannot extract: {exc}")

        # 2) the original archive, last: boto3 closes the file object after uploading it
        f.file.seek(0)
        _put(result, f.file, make_key("zip", rel), rel)
    return result


@router.post("/upload/xlsx")
def upload_xlsx(files: list[UploadFile] = File(...)) -> dict:
    """Store Excel workbooks (.xlsx) under upload/xlsx/."""
    result = _result()
    for f in files:
        rel = clean_relpath(f.filename)
        if not rel.lower().endswith(".xlsx"):
            _reject(result, f.filename, "not an .xlsx file")
            continue
        try:
            with zipfile.ZipFile(f.file) as zf:
                is_workbook = "xl/workbook.xml" in zf.namelist()
        except zipfile.BadZipFile:
            is_workbook = False
        if not is_workbook:
            _reject(result, f.filename, "not a valid Excel workbook")
            continue
        f.file.seek(0)
        _put(result, f.file, make_key("xlsx", rel), rel)
    return result


@router.post("/upload/other")
def upload_other(files: list[UploadFile] = File(...)) -> dict:
    """Store any file under upload/other/."""
    result = _result()
    for f in files:
        rel = clean_relpath(f.filename)
        if not rel:
            _reject(result, f.filename, "missing file name")
            continue
        _put(result, f.file, make_key("other", rel), rel)
    return result


app.include_router(router)
