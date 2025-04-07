import asyncio
import aiohttp
import base64
import subprocess
import sys
import os
from numbers import Number
from typing import Any, Dict

# Define the required fields and their types.
REQUIRED_FIELDS = {
    "current_class_names": list,
    "current_class_probas": list,
    "current_feature_vector": list,
    "current_packet_data": str,
    "current_choice": (str, int),  # Allow string or int for class
    "mel_spec_len": int,
    "mel_spec_num": int,
}

def validate_payload(payload: Dict[str, Any]) -> None:
    """
    Validate that payload contains all required fields with the correct types.
    Raises:
        ValueError: if the payload is missing a key or a field is of an invalid type.
    """
    for key, expected_type in REQUIRED_FIELDS.items():
        if key not in payload:
            raise ValueError(f"Missing required field: {key}")
        # Handle tuple of expected types (for example current_choice can be str or int)
        if isinstance(expected_type, tuple):
            if not any(isinstance(payload[key], t) for t in expected_type):
                expected_names = ", ".join(t.__name__ for t in expected_type)
                raise ValueError(
                    f"Field '{key}' must be one of types ({expected_names}), got {type(payload[key]).__name__}"
                )
        else:
            if not isinstance(payload[key], expected_type):
                raise ValueError(
                    f"Field '{key}' must be of type {expected_type.__name__}, got {type(payload[key]).__name__}"
                )
    
    # Validate that current_class_names is a list of strings.
    for i, name in enumerate(payload["current_class_names"]):
        if not isinstance(name, str):
            raise ValueError(
                f"Element {i} in 'current_class_names' must be a string, got {type(name).__name__}"
            )
    
    # Validate that current_class_probas is a list of numbers.
    for i, p in enumerate(payload["current_class_probas"]):
        if not isinstance(p, Number):
            raise ValueError(
                f"Element {i} in 'current_class_probas' must be a number, got {type(p).__name__}"
            )
    
    # Validate that current_feature_vector is a 2D list of numbers.
    for i, row in enumerate(payload["current_feature_vector"]):
        if not isinstance(row, list):
            raise ValueError(
                f"Row {i} in 'current_feature_vector' must be a list, got {type(row).__name__}"
            )
        for j, item in enumerate(row):
            if not isinstance(item, Number):
                raise ValueError(
                    f"Element [{i}][{j}] in 'current_feature_vector' must be a number, got {type(item).__name__}"
                )
    
    # Validate that 'current_packet_data' is valid base64.
    try:
        base64.b64decode(payload["current_packet_data"])
    except Exception as e:
        raise ValueError("Field 'current_packet_data' is not valid base64 data.") from e

async def send_packet(payload: Dict[str, Any], url: str = "http://127.0.0.1:8090/update") -> None:
    """
    Validate the payload and send it as a JSON POST to the given URL.

    Args:
        payload (dict): The payload to send.
        url (str): The URL of the server endpoint.
    Raises:
        ValueError: if the payload does not validate.
    """
    # Validate payload fields and types.
    validate_payload(payload)
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            resp_json = await response.json()
            print("Response from GUI:", resp_json)

def launch_gui_process():
    """
    Launch the GUI process by spawning a new Python process running custom_gui2.py.
    
    Returns:
        subprocess.Popen: The process handle for the launched GUI process.
        
    Raises:
        FileNotFoundError: if the custom_gui2.py script cannot be found.
    """
    # Assuming custom_gui2.py is in the same directory as this interface module.
    gui_script = os.path.join(os.path.dirname(__file__), "custom_gui2.py")
    if not os.path.exists(gui_script):
        raise FileNotFoundError(f"GUI script not found at: {gui_script}")
    return subprocess.Popen([sys.executable, gui_script])

# If the module is run directly, use a sample payload.
if __name__ == "__main__":
    import numpy as np
    import random

    # Create a sample valid payload.
    CLASS_NAMES = ['chainsaw', 'fire', 'fireworks', 'gun']
    MEL_SPEC_NUM = 20
    MEL_SPEC_LEN = 20

    # Generate random probabilities and normalize.
    probas = np.random.rand(len(CLASS_NAMES))
    probas /= probas.sum()
    
    # Create a random 2D feature vector.
    feature_vector = np.random.rand(MEL_SPEC_NUM, MEL_SPEC_LEN).tolist()
    
    # Generate random packet data (928 bytes total) and encode it.
    packet_data = np.random.bytes(12 + 800 + 16)
    packet_data_b64 = base64.b64encode(packet_data).decode('utf-8')
    
    sample_payload = {
        "current_class_names": CLASS_NAMES,
        "current_class_probas": probas.tolist(),
        "current_feature_vector": feature_vector,
        "current_packet_data": packet_data_b64,
        "current_choice": random.choice(CLASS_NAMES),
        "mel_spec_len": MEL_SPEC_LEN,
        "mel_spec_num": MEL_SPEC_NUM,
    }

    async def main():
        try:
            await send_packet(sample_payload)
        except ValueError as e:
            print("Validation error:", e)
    
    asyncio.run(main())
