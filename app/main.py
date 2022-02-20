from fastapi import FastAPI
from .routers import now, chat

app = FastAPI()

app.include_router(now.router)
app.include_router(chat.router)

