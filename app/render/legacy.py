"""The original parser, preserved verbatim for backward compatibility.

This module is **frozen**. It reproduces the pre-rewrite output of
``POST /convert/hl7/json`` exactly, including its defects:

* segments split on ``\\n`` rather than ``\\r``;
* repeated segments overwriting each other, so only the last survives;
* ``^`` split before ``~``, which fuses distinct repetitions and invents field
  paths such as ``PID.3.4.1``;
* empty, space-only and explicitly-nulled fields dropped or conflated.

Those bugs are the contract someone already has in a script, so reproducing them
is deliberate. **Do not "fix" anything here** -- the corrected implementation is
``app.parsing.parser`` and is served from ``/api/v2/parse``. This shim exists so
existing callers keep working until the sunset date, and
``tests/test_legacy_contract.py`` pins its output against a golden file.

The field-name maps below are equally frozen, including ``PID.12`` being
labelled "County Code" (it is Country Code). The versioned definition store
replaces them for the v2 endpoint.
"""

from __future__ import annotations

from typing import Any

MSH_MAP = {
    'MSH.1': 'Field Separator',
    'MSH.2': 'Encoding Characters',
    'MSH.3': 'Sending Application',
    'MSH.4': 'Sending Facility',
    'MSH.5': 'Receiving Application',
    'MSH.6': 'Receiving Facility',
    'MSH.7': 'Date / Time of Message',
    'MSH.8': 'Security',
    'MSH.9': 'Message Type',
    'MSH.10': 'Message Control ID',
    'MSH.11': 'Processing ID',
    'MSH.12': 'Version ID',
    'MSH.13': 'Sequence Number',
    'MSH.14': 'Continuation Pointer',
    'MSH.15': 'Accept Acknowledgement Type',
    'MSH.16': 'Application Acknowledgement Type',
    'MSH.17': 'Country Code',
    'MSH.18': 'Character Set',
    'MSH.19': 'Principal Language of Message',
}

PID_MAP = {
    'PID.1': 'Set ID - Patient ID',
    'PID.2': 'Patient ID (External ID)',
    'PID.3': 'Patient ID (Internal ID)',
    'PID.4': 'Alternate Patient ID',
    'PID.5': 'Patient Name',
    'PID.5.1': 'Family Name',
    'PID.5.2': 'Given Name',
    'PID.5.3': 'Middle Initial Or Name',
    'PID.5.4': 'Suffix',
    'PID.5.5': 'Prefix',
    'PID.5.6': 'Degree',
    'PID.5.7': 'Name Type Code',
    'PID.5.8': 'Name Representation Code',
    'PID.6': "Mother's Maiden Name",
    'PID.7': 'Date of Birth',
    'PID.8': 'Sex',
    'PID.9': 'Patient Alias',
    'PID.10': 'Race',
    'PID.11': 'Patient Address',
    'PID.11.1': 'Street Address',
    'PID.11.2': ' Other Designation',
    'PID.11.3': 'City',
    'PID.11.4': 'State Or Province',
    'PID.11.5': 'Zip Or Postal Code',
    'PID.11.6': 'Country',
    'PID.11.7': 'Address Type',
    'PID.11.8': 'Other Geographic Designation',
    'PID.11.9': 'County/Parish Code',
    'PID.11.10': 'Census Tract',
    'PID.11.11': 'Address Representation Code',
    'PID.11.12': 'Address Validity Range',
    'PID.11.13': 'Effective Date',
    'PID.11.14': 'Expiration Date',
    'PID.12': 'County Code',
    'PID.13': 'Phone Number - Home',
    'PID.14': 'Phone Number - Business',
    'PID.15': 'Primary Language',
    'PID.16': 'Marital Status',
    'PID.17': 'Religion',
    'PID.18': 'Patient Account Number',
    'PID.19': 'SSN Number - Patient',
    'PID.20': "Driver's License Number",
    'PID.21': "Mother's Identifier",
    'PID.22': 'Ethnic Group',
    'PID.23': 'Birth Place',
    'PID.24': 'Multiple Birth Indicator',
    'PID.25': 'Birth Order',
    'PID.26': 'Citizenship',
    'PID.26.1': 'Citizenship Identifier',
    'PID.26.2': 'Citizenship Text',
    'PID.26.3': 'Citizenship Name Of Coding System',
    'PID.26.4': 'Citizenship Alternate Components',
    'PID.26.5': 'Citizenship Alternate Text',
    'PID.26.6': 'Citizenship  Name Of Alternate Coding System',
    'PID.27': 'Veterans Military Status',
    'PID.28': 'Nationality Code',
    'PID.29': 'Patient Death Date and Time',
    'PID.30': 'Patient Death Indicator',
}


def parse(hl7_message: str) -> dict[str, Any]:
    """The original ``HL7Utils.parse``, unchanged."""
    segments = hl7_message.split("\n")
    json_message: dict[str, Any] = {}
    for segment in segments:
        fields = segment.split("|")
        segment_type = fields[0]
        json_segment: dict[str, Any] = {}
        for i, field in enumerate(fields):
            if i == 0:
                continue
            index = i
            if segment_type == "MSH":
                index = index + 1
            field_name = segment_type + "." + str(index)
            if field != " " and field != "":
                if field_name == "MSH.2":
                    json_segment["MSH.1"] = "|"
                    json_segment[field_name.strip()] = field
                    continue
                json_segment[field_name.strip()] = field
                subsegment_values = field.split("^")
                if len(subsegment_values) > 1:
                    for j, subfield_value in enumerate(subsegment_values):
                        field_name = segment_type + "." + str(index) + "." + str(j + 1)
                        if subfield_value != " " and subfield_value != "":
                            json_segment[field_name.strip()] = subfield_value
                            sub_sub = subfield_value.split("~")
                            if len(sub_sub) > 1:
                                for k, second in enumerate(sub_sub):
                                    field_name = (
                                        segment_type + "." + str(index)
                                        + "." + str(j + 1) + "." + str(k + 1)
                                    )
                                    if second != " " and second != "":
                                        json_segment[field_name.strip()] = second
        json_message[segment_type.strip()] = json_segment
    return json_message


def _annotate(json_data: dict[str, Any], segment: str, mapping: dict[str, str]) -> dict[str, Any]:
    values = json_data.get(segment, {})
    return {
        key: {"name": name, "value": values[key]}
        for key, name in mapping.items()
        if key in values
    }


def detailed(json_data: dict[str, Any]) -> dict[str, Any]:
    """The original ``HL7Utils.detailed``: MSH and PID only."""
    return {
        "MSH": _annotate(json_data, "MSH", MSH_MAP),
        "PID": _annotate(json_data, "PID", PID_MAP),
    }


def render(hl7_message: str) -> dict[str, Any]:
    original = parse(hl7_message)
    return {"original": original, "detailed": detailed(original)}
