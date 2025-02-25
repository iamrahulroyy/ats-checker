import uvicorn, os, dotenv

dotenv.load_dotenv()

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8008))
APP_ENV = os.getenv("APP_ENV", "prod")

if __name__ == "__main__":
    print(f"APP_ENV -> {APP_ENV} | PORT -> {PORT} | HOST -> {HOST}")
    uvicorn.run(
        "main:app", host=HOST, port=PORT, reload=True if APP_ENV == "dev" else False
    )
