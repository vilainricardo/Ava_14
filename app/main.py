from fastapi import FastAPI

app = FastAPI(
    title="Ava_14",
    description="Aplicação de integração com a Steam e geração de conteúdo com IA.",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Ava_14 API está funcionando!"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
