import os
from pathlib import Path
from core import db as jdb

OUTPUTS_BASE = Path(__file__).parent.parent / "outputs" / "eight-masters"

STAGES = ["idle", "scripting", "assets", "assembly", "completed"]

def get_stage_path(topic_id: str, stage: str) -> Path:
    """Returns the directory path for a specific stage of a master's reel."""
    path = OUTPUTS_BASE / topic_id / stage
    path.mkdir(parents=True, exist_ok=True)
    return path

def transition_state(topic_id: str, target_stage: str, action: str) -> dict:
    """Handles the state transition logic and directory enforcement."""
    current_state = jdb.get_reel_state(topic_id) or {
        "current_stage": "idle",
        "approval_status": "approved"
    }
    
    # Simple transition logic: 
    # If action is 'approve', move to next stage and set to 'pending'
    # If action is 'reject', keep stage but set to 'rejected'
    
    new_approval = "pending"
    new_stage = current_state["current_stage"]
    
    if action == "approve":
        # Advance to next stage
        idx = STAGES.index(current_state["current_stage"])
        if idx < len(STAGES) - 1:
            new_stage = STAGES[idx + 1]
    elif action == "reject":
        new_approval = "rejected"
    
    jdb.update_reel_state(topic_id, new_stage, new_approval)
    return {"topic_id": topic_id, "new_stage": new_stage, "new_approval": new_approval}
