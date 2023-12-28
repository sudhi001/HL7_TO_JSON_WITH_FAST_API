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
            index = i
            if segment_type == 'MSH': 
                index = index +1
            # Get the field name.
            field_name = segment_type + '.' + str(index)
             # Add the field data to the JSON object.
            if field != ' ' and field != '':
              if field_name == 'MSH.2':
                 json_segment["MSH.1"] = "|"
                 json_segment[field_name.strip()] = field
                 continue
              json_segment[field_name.strip()] = field
              subsegment_values = field.split('^')
              if len(subsegment_values) >1:
                for j, subfieldValue in enumerate(subsegment_values):
                  field_name = segment_type + '.'+ str(index) +  '.' + str(j+1)
                  if subfieldValue != ' ' and subfieldValue != '':
                    json_segment[field_name.strip()] = subfieldValue
                    sub_subsegment_values = subfieldValue.split('~')
                    if len(sub_subsegment_values) >1:
                      for k, second_subfieldValue in enumerate(sub_subsegment_values):
                        field_name = segment_type + '.'+ str(index) +  '.' + str(j+1)+  '.' + str(k+1)
                        if second_subfieldValue != ' ' and second_subfieldValue != '':
                          json_segment[field_name.strip()] = second_subfieldValue

           
          # Add the JSON segment to the JSON message.
          json_message[segment_type.strip()] = json_segment

        # Return the JSON message.
        return json_message
  
  def msh_details(self, json_data):
    msh_map = {
          "MSH.1": "Field Separator",
          "MSH.2": "Encoding Characters",
          "MSH.3": "Sending Application",
          "MSH.4": "Sending Facility",
          "MSH.5": "Receiving Application",
          "MSH.6": "Receiving Facility",
          "MSH.7": "Date / Time of Message",
          "MSH.8": "Security",
          "MSH.9": "Message Type",
          "MSH.10": "Message Control ID",
          "MSH.11": "Processing ID",
          "MSH.12": "Version ID",
          "MSH.13": "Sequence Number",
          "MSH.14": "Continuation Pointer",
          "MSH.15": "Accept Acknowledgement Type",
          "MSH.16": "Application Acknowledgement Type",
          "MSH.17": "Country Code",
          "MSH.18": "Character Set",
          "MSH.19": "Principal Language of Message"
      }
    msh_value = json_data.get("MSH")
    msh_data = {}
    if msh_value:
          for key in msh_map:
              if key in msh_value:
                  msh_data[msh_map[key]] = msh_value[key]
    return msh_data

  def pid_details(self, json_data):
      pid_map= {
        "PID.1": "Set ID - Patient ID",
        "PID.2": "Patient ID (External ID)",
        "PID.3": "Patient ID (Internal ID)",
        "PID.4": "Alternate Patient ID",
        "PID.5": "Patient Name",
        "PID.5.1":"Family Name",
        "PID.5.2":"Given Name",
        "PID.5.3":"Middle Initial Or Name",
        "PID.5.4":"Suffix",
        "PID.5.5":"Prefix",
        "PID.5.6":"Degree",
        "PID.5.7":"Name Type Code",
        "PID.5.8":"Name Representation Code",
        "PID.6": "Mother's Maiden Name",
        "PID.7": "Date of Birth",
        "PID.8": "Sex",
        "PID.9": "Patient Alias",
        "PID.10": "Race",
        "PID.11": "Patient Address",
        "PID.12": "County Code",
        "PID.13": "Phone Number - Home",
        "PID.14": "Phone Number - Business",
        "PID.15": "Primary Language",
        "PID.16": "Marital Status",
        "PID.17": "Religion",
        "PID.18": "Patient Account Number",
        "PID.19": "SSN Number - Patient",
        "PID.20": "Driver's License Number",
        "PID.21": "Mother's Identifier",
        "PID.22": "Ethnic Group",
        "PID.23": "Birth Place",
        "PID.24": "Multiple Birth Indicator",
        "PID.25": "Birth Order",
        "PID.26": "Citizenship",
        "PID.26.1": "Citizenship Identifier",
        "PID.26.2": "Citizenship Text",
        "PID.26.3": "Citizenship Name Of Coding System",
        "PID.26.4": "Citizenship Alternate Components",
         "PID.26.5": "Citizenship Alternate Text",
         "PID.26.6": "Citizenship  Name Of Alternate Coding System",
        "PID.27": "Veterans Military Status",
        "PID.28": "Nationality Code",
        "PID.29": "Patient Death Date and Time",
        "PID.30": "Patient Death Indicator"
      }

      pid_value = json_data.get("PID")
      pid_data = {}
      if pid_value:
        for key in pid_map:
            if key in pid_value:
               pid_data[pid_map[key]] = pid_value[key]
      return pid_data


  def detailed(self, json_data):
      msh_data = self.msh_details(json_data)
      pid_data = self.pid_details(json_data)
      return {"MSH":msh_data,"PID":pid_data}

