from typing import Union
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from src.hl7  import HL7Utils

app = FastAPI()
templates = Jinja2Templates(directory="templates")
parser = HL7Utils()

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
       return templates.TemplateResponse("index.html", {"request": request})




@app.post("/convert/hl7/json")
def convert_hl7_to_json(data: dict):
     json_message =  parser.parse(data.get("message"))
     detaild= parser.detailed(json_message)
     return {"original":json_message,"detailed":detaild}

