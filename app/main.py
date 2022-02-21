from fastapi import FastAPI, status

from .routers import now, chat

app = FastAPI()

app.include_router(now.router)
app.include_router(chat.router)

@app.get("/", status_code=status.HTTP_200_OK)
def health_check():
    return "healthy"