from ddd.domain.master_reel import MasterReel, PipelineStage, ApprovalStatus
from pathlib import Path

class PipelineService:
    def __init__(self, persistence_repo, base_path: Path):
        self.repo = persistence_repo
        self.base_path = base_path
        self.auto_advance = True # Feature Toggle

    def _validate_assets(self, topic_id: str, stage: PipelineStage) -> bool:
        # Check if files exist in the corresponding directory
        stage_dir = self.base_path / topic_id / stage.value
        return stage_dir.exists() and any(stage_dir.iterdir())

    def request_transition(self, topic_id: str, target_stage_str: str, action: str):
        # 1. Load entity
        reel = self.repo.get(topic_id) or MasterReel(topic_id=topic_id)
        
        # 2. Map input
        target_stage = PipelineStage(target_stage_str)
        
        # 3. Validate domain logic + Asset presence
        if not reel.can_transition_to(target_stage):
            raise Exception("Invalid transition attempt")
            
        if action == "approve" and not self._validate_assets(topic_id, reel.current_stage):
            raise Exception(f"Validation failed: No assets found for {reel.current_stage.value}")
            
        # 4. Perform state change
        if action == "approve":
            reel.approval_status = ApprovalStatus.APPROVED
            reel.current_stage = target_stage
            
            # Feature: Auto-Advance
            if self.auto_advance and target_stage != PipelineStage.COMPLETED:
                # Logic to trigger next stage here...
                pass
        elif action == "reject":
            reel.approval_status = ApprovalStatus.REJECTED
        
        # 5. Persist
        self.repo.save(reel)
        return {"status": "ok", "stage": reel.current_stage.value, "approval": reel.approval_status.value}
