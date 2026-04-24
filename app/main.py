from fastapi import FastAPI

app = FastAPI(title="pronunt-config-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

