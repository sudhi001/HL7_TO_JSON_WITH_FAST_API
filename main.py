from typing import Union
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from src.hl7  import HL7Utils

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
       return templates.TemplateResponse("index.html", {"request": request})




@app.post("/convert/hl7/json")
def convert_hl7_to_json(data: dict):
     json_message = HL7Utils().parse(data.get("message"))
     return json_message

