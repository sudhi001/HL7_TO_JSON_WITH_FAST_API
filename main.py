from typing import Union
from hl7apy.parser import parse_message
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
       return templates.TemplateResponse("index.html", {"request": request})


def hl7_to_json(hl7_message):
  """Converts an HL7 message to a JSON object.

  Args:
    hl7_message: The HL7 message to convert.

  Returns:
    A JSON object representing the HL7 message.
  """

  # Split the HL7 message into segments.
  segments = hl7_message.split('\n')

  # Create a JSON object to store the message data.
  json_message = {}

  # Iterate over the segments and add their data to the JSON object.
  for segment in segments:

    # Split the segment into fields.
    fields = segment.split('|')

    # Get the segment type.
    segment_type = fields[0]

    # Create a JSON object to store the segment data.
    json_segment = {}

    # Iterate over the fields and add their data to the JSON object.
    for i, field in enumerate(fields):

      # Skip the segment type field.
      if i == 0:
        continue

      # Get the field name.
      field_name = segment_type + '.' + str(i)

      # Add the field data to the JSON object.
      json_segment[field_name] = field

    # Add the JSON segment to the JSON message.
    json_message[segment_type] = json_segment

  # Return the JSON message.
  return json.dumps(json_message)

@app.post("/convert/hl7/json")
def convert_hl7_to_json(data: dict):
     json_message = hl7_to_json(data.get("message"))
     return json_message

