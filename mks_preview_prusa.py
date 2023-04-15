import argparse
import base64
import re
from os.path import exists
from io import BytesIO
from PIL import Image  # pip install pillow
from typing import List


def rgb2tft(r, g, b):
    # src: mks-wifi plugin : https://github.com/Jeredian/mks-wifi-plugin/blob/develop/MKSPreview.py
    r = r >> 3
    g = g >> 2
    b = b >> 3
    rgb = (r << 11) | (g << 5) | b
    return "{:02x}".format(rgb & 0xFF) + "{:02x}".format(((rgb >> 8) & 0xFF))


def generate_tft(img: Image):
    width, height = img.size
    if width == 100:
        res = ";simage:"
    else:
        res = ";;gimage:"
    pixels = img.convert("RGB")
    for y in range(height):
        for x in range(width):
            r, g, b = pixels.getpixel((x, y))
            res += rgb2tft(r, g, b)
        res += "\nM10086 ;"
    return res


def convert_prusa_thumb_to_tft(prusa_gcode: str) -> List:
    s_pattern = (
        "(; thumbnail begin )([0-9]+)(x)([0-9]+) ([0-9]+)\n(.*?)(?=; thumbnail end)"
    )
    pattern = re.compile(s_pattern, re.M | re.I | re.S)

    tft_gcode = []

    for match in pattern.finditer(prusa_gcode):
        th_width = match.group(2)
        th_height = match.group(4)
        th_size = match.group(5)

        # TODO validate previews size, must be 100x100 or 200x200

        th_data_base64 = match.group(6)
        th_data_base64 = th_data_base64.replace("; ", "").replace("\n", "")
        stream = BytesIO(base64.b64decode(th_data_base64))
        image = Image.open(stream).convert("RGB")
        # TODO remove debug save
        # image.save(f"{th_width}x{th_height}.png", "PNG")
        stream.close()
        tft_gcode.append(generate_tft(image))

    return tft_gcode


def replace_thumbs(prusa_gcode: str, tft_gcode: List):
    s_pattern = f"; thumbnail begin .*; thumbnail end"
    if len(tft_gcode) > 0:
        tft_gcode = "\n".join(tft_gcode) + "\n"
    else:
        tft_gcode = ""
    prusa_gcode = tft_gcode + re.sub(
        s_pattern, "", prusa_gcode, flags=re.M | re.I | re.S
    )
    return prusa_gcode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="MKS Preview for Prusa",
        description="Post processing tool to convert Prusa Slicer generated PNG thumbnails to MKS gcode",
    )
    parser.add_argument("filename")
    parser.add_argument(
        "--cut-thumbs",
        "-c",
        action="store_true",
        help="Remove thumbnails from gcode. Reduces file size.",
        default=False,
    )
    args = parser.parse_args()

    with open(args.filename) as original_gcode_file:
        prusa_gcode = original_gcode_file.read()
        if args.cut_thumbs:
            tft_thumbs = []
        else:
            tft_thumbs = convert_prusa_thumb_to_tft(prusa_gcode)
        prusa_gcode = replace_thumbs(prusa_gcode, tft_thumbs)

    with open(args.filename, "w") as out_gcode_file:
        out_gcode_file.write(prusa_gcode)
