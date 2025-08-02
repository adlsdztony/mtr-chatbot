import regex
import json
import argparse
import pathlib
from typing_extensions import Iterable, Dict, Union


def find_images(md: str) -> Iterable[Dict]:
    """
    Find all image links in the markdown string.

    Args:
        md (str): The markdown content as a string.

    Returns:
        Iterable[Dict]: A generator yielding dictionaries with image link and its position.
    """

    RAW_IMAGE_MD = regex.compile(r"!\[\]\((.*?)\)")
    for match in RAW_IMAGE_MD.finditer(md):
        yield {"link": match.group(1), "index": match.start()}


def encode_image(path: Union[str, pathlib.Path], prefix: bool = False) -> str:
    """
    Encode an image file to a base64 string.
    Args:
        path (Union[str, pathlib.Path]): The path to the image file.
    Returns:
        str: The base64 encoded string of the image.
    """

    import base64

    with open(path, "rb") as f:
        # return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        return (
            f"{base64.b64encode(f.read()).decode('utf-8')}"
            if not prefix
            else f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        )


def form_text(text: str) -> Dict[str, str]:
    return {"type": "text", "text": text}


def form_image(path: Union[str, pathlib.Path]) -> Dict[str, str]:
    return {
        "type": "image",
        "source_type": "base64",
        "data": encode_image(path),
        "mime_type": "image/png",
    }
