from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class PipelineStage(Enum):
    IDLE = "idle"
    SCRIPTING = "scripting"
    ASSETS = "assets"
    ASSEMBLY = "assembly"
    COMPLETED = "completed"

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

@dataclass
class MasterReel:
    topic_id: str
    current_stage: PipelineStage = PipelineStage.IDLE
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    
    def can_transition_to(self, target_stage: PipelineStage) -> bool:
        # If already in the target stage, no transition needed
        if self.current_stage == target_stage:
            return True
            
        # Idle -> Scripting is always allowed to start
        if self.current_stage == PipelineStage.IDLE and target_stage == PipelineStage.SCRIPTING:
            return True
            
        # Any other transition requires approval
        return self.approval_status == ApprovalStatus.APPROVED
