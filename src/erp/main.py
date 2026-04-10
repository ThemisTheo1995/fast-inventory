from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from erp.api.router import api_router

app = FastAPI(title="ERP API")

# Define the origins that are allowed to talk to your API
origins = [
    "http://localhost:5173", # Default Vite port
    "http://127.0.0.1:5173",
    # Add your production domain here later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
