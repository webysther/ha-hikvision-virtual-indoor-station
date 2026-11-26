"""Tests of the brand images, against the specification of Home Assistant.

https://github.com/home-assistant/brands#image-specification
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

BRAND = (
    Path(__file__).parent.parent
    / "custom_components"
    / "hikvision_virtual_indoor_station"
    / "brand"
)


@pytest.mark.parametrize(
    ("name", "size"),
    [
        ("icon.png", 256),
        ("icon@2x.png", 512),
        ("dark_icon.png", 256),
        ("dark_icon@2x.png", 512),
    ],
)
def test_icons(name: str, size: int) -> None:
    """Test that the icons are square PNGs of their size, with transparency."""
    with Image.open(BRAND / name) as image:
        assert image.format == "PNG"
        assert image.size == (size, size)
        assert image.mode == "RGBA"


def test_logo() -> None:
    """Test that the logo is a landscape PNG, its shortest side 128 to 256 pixels."""
    with Image.open(BRAND / "logo.png") as image:
        assert image.format == "PNG"
        assert image.width > image.height
        assert 128 <= image.height <= 256
        # Trimmed: the logo touches every edge
        assert image.getbbox() == (0, 0, image.width, image.height)


def test_only_known_images() -> None:
    """Test that the folder holds only images Home Assistant serves."""
    assert {path.name for path in BRAND.iterdir()} <= {
        "icon.png",
        "icon@2x.png",
        "logo.png",
        "logo@2x.png",
        "dark_icon.png",
        "dark_icon@2x.png",
        "dark_logo.png",
        "dark_logo@2x.png",
    }
