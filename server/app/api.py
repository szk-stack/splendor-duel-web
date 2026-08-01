"""REST 端点：创建/加入房间。"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .rooms import RoomError, RoomManager

router = APIRouter(prefix="/api")


class NicknameBody(BaseModel):
    nickname: str = Field(..., max_length=16)
    ai: bool = False  # 人机模式：slot 1 为 AI 玩家


def get_manager(request: Request) -> RoomManager:
    return request.app.state.manager


def _err_response(e: RoomError):
    return JSONResponse(status_code=e.http, content={"code": e.code, "message": e.message})


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/rooms")
async def create_room(body: NicknameBody, manager: RoomManager = Depends(get_manager)):
    try:
        code, token, slot = manager.create(body.nickname, ai=body.ai)
    except RoomError as e:
        return _err_response(e)
    return {"room_code": code, "token": token, "slot": slot}


@router.post("/rooms/{code}/join")
async def join_room(code: str, body: NicknameBody,
                    manager: RoomManager = Depends(get_manager)):
    try:
        room_code, token, slot = manager.join(code, body.nickname)
    except RoomError as e:
        return _err_response(e)
    return {"room_code": room_code, "token": token, "slot": slot}
