import json

class HL7Utils:
  def __init__(self):
     pass

  def parse(self, hl7_message):
        """Converts an HL7 message to a JSON object.

        Args:
          hl7_message: The HL7 message to convert.

        Returns:
          A JSON object representing the HL7 message.
        """
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
            if field != ' ' and field != '':
              json_segment[field_name] = field
              if field_name == 'MSH.1':
                continue
              subsegment_values = field.split('^')
              if len(subsegment_values) >1:
                for j, subfieldValue in enumerate(subsegment_values):
                  field_name = field_name +  '.' + str(j+1)
                  if subfieldValue != ' ' and subfieldValue != '':
                    json_segment[field_name] = subfieldValue
                    sub_subsegment_values = subfieldValue.split('~')
                    if len(sub_subsegment_values) >1:
                      for k, second_subfieldValue in enumerate(sub_subsegment_values):
                        field_name = field_name +  '.' + str(k+1)
                        if second_subfieldValue != ' ' and second_subfieldValue != '':
                          json_segment[field_name] = second_subfieldValue

           
          # Add the JSON segment to the JSON message.
          json_message[segment_type] = json_segment

        # Return the JSON message.
        return json.dumps(json_message)