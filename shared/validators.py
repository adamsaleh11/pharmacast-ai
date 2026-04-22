from collections.abc import Mapping


FORBIDDEN_FIELDS = {
    "patient_id",
    "patient_name",
    "patient_dob",
    "prescriber_id",
    "prescriber_name",
}


def validate_no_patient_data(payload: dict) -> None:
    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            for key, nested_value in value.items():
                if key in FORBIDDEN_FIELDS:
                    raise ValueError(
                        f"Patient data field '{key}' found in LLM payload — this is not permitted"
                    )
                walk(nested_value)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
