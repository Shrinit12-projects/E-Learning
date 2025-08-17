import json
import asyncio
from typing import Dict, Any, Set
from redis.asyncio import Redis
from fastapi import WebSocket
from pymongo.database import Database
from services import analytics_service

class RealTimeAnalytics:
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}  # course_id -> websockets
        self.instructor_connections: Dict[str, WebSocket] = {}  # instructor_id -> websocket

    async def connect_instructor(self, instructor_id: str, websocket: WebSocket):
        await websocket.accept()
        self.instructor_connections[instructor_id] = websocket

    async def disconnect_instructor(self, instructor_id: str):
        self.instructor_connections.pop(instructor_id, None)

    async def connect_course(self, course_id: str, websocket: WebSocket):
        await websocket.accept()
        if course_id not in self.connections:
            self.connections[course_id] = set()
        self.connections[course_id].add(websocket)

    async def disconnect_course(self, course_id: str, websocket: WebSocket):
        if course_id in self.connections:
            self.connections[course_id].discard(websocket)
            if not self.connections[course_id]:
                del self.connections[course_id]

    async def broadcast_course_update(self, course_id: str, data: Dict[str, Any]):
        if course_id in self.connections:
            dead_connections = set()
            for websocket in self.connections[course_id]:
                try:
                    await websocket.send_json(data)
                except:
                    dead_connections.add(websocket)
            
            # Clean up dead connections
            for ws in dead_connections:
                self.connections[course_id].discard(ws)

    async def broadcast_to_instructor(self, instructor_id: str, data: Dict[str, Any]):
        if instructor_id in self.instructor_connections:
            try:
                await self.instructor_connections[instructor_id].send_json(data)
            except:
                self.instructor_connections.pop(instructor_id, None)

realtime_analytics = RealTimeAnalytics()

async def publish_analytics_update(r: Redis, event_type: str, course_id: str, data: Dict[str, Any]):
    """Publish analytics update to Redis pub/sub"""
    try:
        from repos.helper import JSONEncoder
        message = {
            "event": event_type,
            "course_id": course_id,
            "data": data,
            "timestamp": data.get("generated_at")
        }
        channel = f"analytics:{course_id}"
        print(f"Publishing to {channel}: {event_type}")
        await r.publish(channel, json.dumps(message, cls=JSONEncoder))
        

            
    except Exception as e:
        print(f"Error publishing analytics update: {e}")

async def listen_analytics_updates(r: Redis, db: Database):
    """Listen for analytics updates and broadcast to WebSocket connections"""
    while True:
        try:
            print("Starting analytics listener...")
            pubsub = r.pubsub()
            await pubsub.psubscribe("analytics:*")
            print("Subscribed to analytics:*")
            
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    try:
                        data = json.loads(message["data"])
                        course_id = data["course_id"]
                        print(f"Processing update for course: {course_id}")
                        
                        if course_id == "platform":
                            # Handle platform updates
                            platform_data = await analytics_service.platform_overview(db, r)
                            platform_message = {
                                "event": "platform_overview",
                                "data": platform_data
                            }
                            # Broadcast to all instructor connections
                            for instructor_id in realtime_analytics.instructor_connections:
                                await realtime_analytics.broadcast_to_instructor(instructor_id, platform_message)
                        else:
                            # Handle course-specific updates
                            fresh_data = await analytics_service.course_performance(db, r, course_id)
                            update_message = {
                                "event": "course_analytics_update",
                                "course_id": course_id,
                                "analytics": fresh_data
                            }
                            # Broadcast to course connections
                            await realtime_analytics.broadcast_course_update(course_id, update_message)
                        
                    except Exception as e:
                        print(f"Error processing analytics update: {e}")
                        
        except Exception as e:
            print(f"Redis connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)