from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ddd.application.pipeline_service import PipelineService
from ddd.infrastructure.reel_repository import ReelRepository
from pathlib import Path

router = APIRouter()
repo = ReelRepository()
# Using a base path within content-creator outputs
service = PipelineService(repo, base_path=Path(__file__).parent.parent.parent / "outputs" / "eight-masters")

class TransitionRequest(BaseModel):
    topic_id: str
    target_stage: str
    action: str

@router.post("/transition")
async def transition_reel(req: TransitionRequest):
    try:
        return service.request_transition(req.topic_id, req.target_stage, req.action)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
