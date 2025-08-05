import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import requests
import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel


# Configuration
class Config:
    API_KEY_HEADER = "X-API-Key"
    REQUEST_TIMEOUT = 5
    JOB_PROCESSING_STEPS = 5
    STEP_DURATION = 2

    # Mock optimization results
    MOCK_RESULTS = {
        "energy_savings_kwh": 245.8,
        "cost_reduction_eur": 48.72,
        "co2_reduction_kg": 98.32,
        "optimization_score": 0.85,
        "recommended_actions": [
            "Reduce HVAC temperature by 2°C during off-peak hours",
            "Implement smart lighting controls in zone B",
            "Schedule high-energy equipment during low-cost periods",
        ],
    }


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory job storage
jobs_storage: Dict[str, Dict[str, Any]] = {}

# FastAPI app
app = FastAPI(
    title="DSS Mock API",
    description="Mock Decision Support System for energy optimization integration",
    version="1.0.0",
)

# API Key authentication
api_key_header = APIKeyHeader(name=Config.API_KEY_HEADER, auto_error=False)


def get_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Validate API key from request header."""

    expected_key = os.getenv("BACKEND_API_KEY")

    if expected_key and api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    return api_key


# Pydantic models
class F1JobRequest(BaseModel):
    building_id: str = "building_001"
    optimization_type: str = "energy_efficiency"
    parameters: Dict[str, Any] = {}


class F1JobResponse(BaseModel):
    job_id: str
    status: str
    message: str
    created_at: str


class F1JobStatus(BaseModel):
    job_id: str
    status: str
    progress: int
    result: Optional[Dict[str, Any]] = None
    created_at: str
    completed_at: Optional[str] = None


# Job processing functions
def update_job_progress(job_id: str, status: str, progress: int) -> None:
    """Update job status and progress in storage."""

    if job_id in jobs_storage:
        jobs_storage[job_id]["status"] = status
        jobs_storage[job_id]["progress"] = progress


def complete_job(job_id: str) -> None:
    """Mark job as completed with results."""

    if job_id in jobs_storage:
        jobs_storage[job_id]["status"] = "completed"
        jobs_storage[job_id]["progress"] = 100
        jobs_storage[job_id]["completed_at"] = datetime.now().isoformat()
        jobs_storage[job_id]["result"] = Config.MOCK_RESULTS


def fail_job(job_id: str, error: str) -> None:
    """Mark job as failed with error message."""

    if job_id in jobs_storage:
        jobs_storage[job_id]["status"] = "failed"
        jobs_storage[job_id]["error"] = error


async def send_webhook(callback_url: str, job_id: str) -> None:
    """Send webhook notification for completed job."""

    try:
        callback_data = {
            "job_id": job_id,
            "status": "completed",
            "result": jobs_storage[job_id]["result"],
        }

        requests.post(callback_url, json=callback_data, timeout=Config.REQUEST_TIMEOUT)
        logger.info(f"Webhook sent to {callback_url} for job {job_id}")
    except Exception as e:
        logger.error(f"Webhook failed for job {job_id}: {e}")


async def simulate_job_processing(
    job_id: str, callback_url: Optional[str] = None
) -> None:
    """Simulate energy optimization job processing."""

    try:
        update_job_progress(job_id, "running", 10)

        # Simulate processing steps
        progress_steps = [25, 50, 75, 90]
        for progress in progress_steps:
            await asyncio.sleep(Config.STEP_DURATION)
            update_job_progress(job_id, "running", progress)

        await asyncio.sleep(Config.STEP_DURATION)
        complete_job(job_id)

        if callback_url:
            await send_webhook(callback_url, job_id)

    except Exception as e:
        logger.error(f"Job processing failed for {job_id}: {e}")
        fail_job(job_id, str(e))


# Utility functions
def validate_job_exists(job_id: str) -> Dict[str, Any]:
    """Validate job exists and return job data."""

    if job_id not in jobs_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    return jobs_storage[job_id]


def validate_job_cancellable(job_data: Dict[str, Any]) -> None:
    """Validate job can be cancelled."""

    if job_data["status"] in ["completed", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel completed or failed job",
        )


# API endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""

    return {"status": "healthy", "service": "DSS Mock API"}


@app.post("/f1/jobs", response_model=F1JobResponse)
async def create_f1_job(
    job_request: F1JobRequest,
    background_tasks: BackgroundTasks,
    callback_url: Optional[str] = None,
    _: str = Depends(get_api_key),
):
    """Create energy optimization analysis job."""

    job_id = str(uuid.uuid4())

    job_data = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "building_id": job_request.building_id,
        "optimization_type": job_request.optimization_type,
        "parameters": job_request.parameters,
        "created_at": datetime.now().isoformat(),
        "callback_url": callback_url,
    }

    jobs_storage[job_id] = job_data
    background_tasks.add_task(simulate_job_processing, job_id, callback_url)

    logger.info(f"Created job {job_id} for building {job_request.building_id}")

    return F1JobResponse(
        job_id=job_id,
        status="pending",
        message=f"Energy optimization job created for building {job_request.building_id} ({job_request.optimization_type})",
        created_at=job_data["created_at"],
    )


@app.get("/f1/jobs/{job_id}", response_model=F1JobStatus)
async def get_job_status(job_id: str, _: str = Depends(get_api_key)):
    """Get energy optimization job status."""

    job_data = validate_job_exists(job_id)

    return F1JobStatus(
        job_id=job_id,
        status=job_data["status"],
        progress=job_data["progress"],
        result=job_data.get("result"),
        created_at=job_data["created_at"],
        completed_at=job_data.get("completed_at"),
    )


@app.get("/f1/jobs")
async def list_jobs(_: str = Depends(get_api_key)):
    """List all energy optimization jobs."""

    return {"jobs": list(jobs_storage.values())}


@app.delete("/f1/jobs/{job_id}")
async def cancel_job(job_id: str, _: str = Depends(get_api_key)):
    """Cancel energy optimization job."""

    job_data = validate_job_exists(job_id)
    validate_job_cancellable(job_data)

    jobs_storage[job_id]["status"] = "cancelled"
    logger.info(f"Cancelled job {job_id}")

    return {"message": f"Job {job_id} cancelled"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
