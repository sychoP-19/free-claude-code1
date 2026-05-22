from ddd.domain.master_reel import MasterReel, PipelineStage, ApprovalStatus

# In-memory mock for now, to be replaced by SQL implementation
_db = {}

class ReelRepository:
    def get(self, topic_id: str) -> Optional[MasterReel]:
        if topic_id in _db:
            data = _db[topic_id]
            return MasterReel(
                topic_id=topic_id,
                current_stage=PipelineStage(data["stage"]),
                approval_status=ApprovalStatus(data["approval"])
            )
        return None

    def save(self, reel: MasterReel):
        _db[reel.topic_id] = {
            "stage": reel.current_stage.value,
            "approval": reel.approval_status.value
        }
