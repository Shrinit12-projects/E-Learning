from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, FastAPI
from redis.asyncio import Redis
from pymongo.database import Database
from deps import get_db, get_redis
from auth.dependencies import get_current_user
from services.realtime_analytics import realtime_analytics
from services import analytics_service

router = APIRouter(prefix="/realtime", tags=["realtime"])

@router.websocket("/analytics/{course_id}")
async def course_analytics_websocket(websocket: WebSocket, course_id: str):
    app: FastAPI = websocket.app
    db = app.state.db
    r = app.state.redis
    
    await realtime_analytics.connect_course(course_id, websocket)
    
    try:
        initial_data = await analytics_service.course_performance(db, r, course_id)
        await websocket.send_json({
            "event": "initial_data",
            "course_id": course_id,
            "analytics": initial_data
        })
        
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        await realtime_analytics.disconnect_course(course_id, websocket)

@router.websocket("/instructor/{instructor_id}")
async def instructor_dashboard_websocket(websocket: WebSocket, instructor_id: str):
    app: FastAPI = websocket.app
    db = app.state.db
    r = app.state.redis
    
    await realtime_analytics.connect_instructor(instructor_id, websocket)
    
    try:
        platform_data = await analytics_service.platform_overview(db, r)
        await websocket.send_json({
            "event": "platform_overview",
            "data": platform_data
        })
        
        while True:
            await websocket.receive_text()
            
    except WebSocketDisconnect:
        await realtime_analytics.disconnect_instructor(instructor_id)