"""Streaming analysis routes with WebSockets."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import asyncio
import json
import time
from typing import Dict, Any
from app.ai.orchestrator import DeterministicOrchestrator
from app.utils.logger import logger

router = APIRouter()

class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.active_connections: list = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Active: {len(self.active_connections)}")
    
    async def send_message(self, websocket: WebSocket, message: Dict[str, Any]):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all active connections."""
        for connection in self.active_connections:
            await self.send_message(connection, message)

manager = ConnectionManager()

@router.websocket("/ws/analyze")
async def streaming_analyze(websocket: WebSocket):
    """WebSocket endpoint for streaming analysis."""
    await manager.connect(websocket)
    
    try:
        # Receive request
        data = await websocket.receive_json()
        resume = data.get("resume", "")
        jd_text = data.get("jd_text", "")
        jd_url = data.get("jd_url", "")
        
        if not resume:
            await manager.send_message(websocket, {
                "type": "error",
                "message": "Resume text is required"
            })
            return
        
        # Send progress updates
        steps = [
            {"step": 1, "message": "Reading resume and job description...", "progress": 20},
            {"step": 2, "message": "Analyzing semantic alignment...", "progress": 40},
            {"step": 3, "message": "Identifying friction points...", "progress": 60},
            {"step": 4, "message": "Generating skill gap analysis...", "progress": 80},
            {"step": 5, "message": "Creating learning roadmap...", "progress": 95},
        ]
        
        # Handle JD from URL if provided
        if jd_url and not jd_text:
            from app.utils.jd_extractor import JDExtractor
            extractor = JDExtractor()
            jd_result = await extractor.extract(jd_url)
            if jd_result:
                jd_text = jd_result.get("text", "")
                await manager.send_message(websocket, {
                    "type": "info",
                    "message": f"Extracted JD from: {jd_result.get('title', 'Unknown position')}"
                })
        
        # Send progress updates
        for step_info in steps:
            await manager.send_message(websocket, {
                "type": "progress",
                "step": step_info["step"],
                "message": step_info["message"],
                "progress": step_info["progress"]
            })
            await asyncio.sleep(0.5)
        
        # Process analysis
        orchestrator = DeterministicOrchestrator()
        result = await orchestrator.process({
            "resume": resume,
            "jd_text": jd_text,
            "jd_url": jd_url
        })
        
        # Send complete result
        await manager.send_message(websocket, {
            "type": "complete",
            "data": result,
            "timestamp": time.time()
        })
        
        logger.info("WebSocket analysis completed successfully")
        
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected")
    except json.JSONDecodeError:
        await manager.send_message(websocket, {
            "type": "error",
            "message": "Invalid JSON received"
        })
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.send_message(websocket, {
            "type": "error",
            "message": str(e)
        })
    finally:
        if websocket in manager.active_connections:
            manager.disconnect(websocket)

@router.get(
    "/ws/health",
    summary="WebSocket health check"
)
async def websocket_health():
    """Check WebSocket service health."""
    return {
        "status": "ok",
        "active_connections": len(manager.active_connections),
        "max_connections": 100
    }
