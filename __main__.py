import uvicorn
from main import app

uvicorn.run(app, port=1138, lifespan="on")
