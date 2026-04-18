from fastapi import FastAPI

from app.api.routes import route_optimizer, user_profile

app = FastAPI(title="Pacer AI", version="0.1.0")

app.include_router(route_optimizer.router)
app.include_router(user_profile.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
