"""Reel Producer API Routes - standalone module for easy importing."""
import json
from pathlib import Path
from fastapi import Request, WebSocket
from fastapi.responses import JSONResponse, FileResponse

# Will be imported at call time
# from core.websocket_manager import manager
# from core import db as jdb
# from pipelines import reel_production as p_reel_prod


async def reel_topics(request: Request):
    """Trigger topic discovery via trend_miner.run().

    POST /api/reel/topics {"query": "fitness", "platform": "youtube", "window": "7 days"}
    """
    body = await request.json()
    query = str(body.get("query", ""))
    platform = str(body.get("platform", "youtube"))
    window = str(body.get("window", "7 days"))

    if not query:
        return JSONResponse({"status": "error", "message": "query required"}, status_code=400)

    try:
        from agents.trend_miner import run as trend_miner_run
        result = await trend_miner_run(query=query, platform=platform, window=window)
        return {"status": "ok", "topics": result.get("topics", []), "summary": result.get("summary", {})}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def reel_select_topics(request: Request):
    """Store user topic selection (1-2 topic_ids).

    POST /api/reel/select-topics {"topic_ids": ["topic_001", "topic_002"], "platform": "youtube"}
    """
    body = await request.json()
    topic_ids = body.get("topic_ids", [])
    platform = str(body.get("platform", "youtube"))

    if not topic_ids or len(topic_ids) > 2:
        return JSONResponse({"status": "error", "message": "Select 1-2 topic_ids"}, status_code=400)

    try:
        from core import db as jdb
        created_ids = []
        for tid in topic_ids:
            if isinstance(tid, dict):
                title = tid.get("title", tid.get("id", ""))
                metadata = tid
                topic_id = tid.get("id", str(tid))
            else:
                title = tid
                metadata = {"id": tid}
                topic_id = str(tid)
            created_ids.append(jdb.reel_select_topic(topic_id=topic_id, title=title, platform=platform, metadata=metadata))

        return {"status": "ok", "selected_count": len(topic_ids), "ids": created_ids}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def reel_start(request: Request):
    """Start pipeline with reel_production.run().

    POST /api/reel/start {"topic_id": "topic_001", "topic_title": "My Topic", "platforms": ["youtube", "tiktok"]}
    """
    body = await request.json()
    topic_id = str(body.get("topic_id", ""))
    topic_title = str(body.get("topic_title", ""))
    platforms = body.get("platforms", ["youtube"])

    if not topic_id:
        return JSONResponse({"status": "error", "message": "topic_id required"}, status_code=400)

    try:
        from core import db as jdb
        jdb.reel_start_production(topic_id)
    except Exception:
        pass

    try:
        from pipelines import reel_production as p_reel_prod

        pipeline_payload = {
            "topic": topic_title or topic_id,
            "topic_id": topic_id,
            "style": "shorts",
            "tone": "viral",
            "platforms": platforms if isinstance(platforms, list) else [platforms],
        }

        result = await p_reel_prod.run(pipeline_payload)

        output_path = result.get("output_path", "")
        script_metadata = result.get("result_summary", {}).get("stages", {}).get("stage2_script", {})
        duration_s = result.get("result_summary", {}).get("stages", {}).get("stage4_assembly", {}).get("duration_s", 0)

        for platform in platforms if isinstance(platforms, list) else [platforms]:
            try:
                from core import db as jdb
                jdb.reel_complete(
                    topic_id=topic_id,
                    title=f"{topic_title} - {platform.title()}",
                    platform=platform,
                    output_path=output_path,
                    script=script_metadata,
                    duration_s=duration_s,
                    topic_title=topic_title
                )
            except Exception:
                pass

        return {"status": "ok", **result}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def reel_approve_script(request: Request):
    """Advance pipeline after script review.

    POST /api/reel/approve-script {"topic_id": "topic_001", "approved": true, "notes": "Looks good"}
    """
    body = await request.json()
    topic_id = str(body.get("topic_id", ""))
    approved = bool(body.get("approved", True))
    notes = str(body.get("notes", ""))

    if not topic_id:
        return JSONResponse({"status": "error", "message": "topic_id required"}, status_code=400)

    if not approved:
        return {"status": "ok", "approved": False, "message": "Script rejected", "notes": notes}

    try:
        from core.websocket_manager import manager
        await manager.log(f"Script approved for {topic_id}", "success")
        return {"status": "ok", "approved": True, "message": "Script approved. Pipeline will continue."}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def reel_pending():
    """List completed reels from database."""
    try:
        from core import db as jdb
        completed = jdb.reel_get_completed()
        return {"status": "ok", "reels": completed}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


async def reel_download(topic_id_platform: str):
    """Return file download.

    GET /api/reel/download/topic_001_youtube
    """
    parts = topic_id_platform.rsplit("_", 1)
    if len(parts) != 2:
        return JSONResponse({"status": "error", "message": "Invalid format. Use topicid_platform"}, status_code=400)

    topic_id, platform = parts
    file_path = f"outputs/{topic_id}_{platform}.mp4"
    path = Path(__file__).parent / file_path

    if not path.exists():
        return JSONResponse({"status": "error", "message": "File not found"}, status_code=404)

    return FileResponse(path, filename=f"{topic_id}_{platform}.mp4")


async def ws_reel(websocket: WebSocket):
    """Broadcast pipeline progress.

    Connect to receive real-time updates on reel production pipeline.
    """
    from core.websocket_manager import manager

    await manager.connect(websocket)
    try:
        await manager.log("Reel producer WebSocket connected", "info")
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except Exception:
        manager.disconnect(websocket)