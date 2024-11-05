#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import shutil
import subprocess
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('--dir', '-d', type=str, help='Directory', required=True)
parser.add_argument('--file', '-f', type=str, help='File', required=True)
parser.add_argument('--sizecheck', '-s', type=int, help='Upscale when the image size is smaller than this.', default=3840)
parser.add_argument('--cpu', '-c', help='Upscale with CPU? Will convert the images to JPG', action=argparse.BooleanOptionalAction, required=False)

args = parser.parse_args()
directory = Path(args.dir)
filename  = args.file
sizecheck = args.sizecheck
cpu       = args.cpu

filepath = Path(directory / filename)
if filepath.exists():
    with Image.open(filepath) as img:
        width, height = img.size
else:
    print("File does not exist!")
    exit(1)

upscale = False
if (width / height) < 1.0:
    if height < sizecheck:
        upscale = True
elif width < sizecheck:
    upscale = True

if upscale:
    filetimes = (filepath.stat().st_atime, filepath.stat().st_mtime)
    # CPU upscaling seems to require JPG. Not sure why but PNG sometimes fails.
    if cpu and filepath.suffix == ".png":
        with Image.open(filepath) as img:
            rgb_im = img.convert('RGB')
            filepath_jpg = filepath.with_suffix('.jpg')
            rgb_im.save(filepath_jpg, quality=100, subsampling=0)
            if filepath_jpg.exists():
                # Update modification times.
                os.utime(filepath_jpg, filetimes)
                # Delete original file
                filepath.unlink()
                # Move metadata to use the correct extension.
                filepath_metadata = filepath.with_suffix(filepath.suffix + ".json")
                if filepath_metadata.exists():
                    filepath_metadata_jpg = filepath_jpg.with_suffix(filepath_jpg.suffix + ".json")
                    shutil.move(filepath_metadata, filepath_metadata_jpg)
                    filepath_metadata = filepath_metadata_jpg
                filepath = filepath_jpg
            else:
                print("ERROR: Failed to convert to jpg!")

    # Upscale X2.
    subprocess.Popen(['waifu2x-ncnn-vulkan', '-i', filepath, '-o', filepath, '-s', '2', '-g', '-1' if cpu else '0']).wait()
    # Update modification times.
    os.utime(filepath, filetimes)
    print(f"{filepath.name} was upscaled by X2.")
else:
    print(f"No upscale needed for {filepath.name} because the size is {width}x{height}.")
