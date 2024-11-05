#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import subprocess
from py7zr import pack_7zarchive, unpack_7zarchive
import shutil

shutil.register_archive_format('7zip', pack_7zarchive, description='7zip archive')
shutil.register_unpack_format('7zip', ['.7z'], unpack_7zarchive)

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
filepath_metadata = filepath.with_suffix(filepath.suffix + ".json")

name = Path(filename).stem
extractdir = directory / name
shutil.unpack_archive(filepath, extractdir)

# Delete unwanted folders.
path_macosx = extractdir / "__MACOSX"
if path_macosx.exists():
    shutil.rmtree(path_macosx)

# Find the supported files.
types = ('**/*.png', '**/*.jpg', '**/*.jpeg', '**/*.bmp', '**/*.webp', '**/*.gif', '**/*.mp4')
extracted_files:list[Path] = []
for files in types:
    extracted_files.extend(extractdir.glob(files))

# Copy the JSON from the archive and move the extracted files to the root dir.
scriptdir = Path(__file__).absolute().parent
for path in extracted_files:
    # Update modification time to what the archive is set to.
    os.utime(path, (filepath.stat().st_atime, filepath.stat().st_mtime))
    # Move the file to the root directory.
    newpath = directory / Path(path.stem + " - " + filepath.stem + path.suffix)
    shutil.move(path, newpath)
    if filepath_metadata.exists():
        shutil.copy(filepath_metadata, newpath.with_suffix(newpath.suffix + ".json"))

    # Upscale if needed.
    subprocess.Popen([scriptdir / 'gallery-dl-upscale.py', '--dir', directory, '--file', newpath.name, '--sizecheck', f"{args.sizecheck}", '--cpu' if cpu else '--no-cpu']).wait()

# Cleanup.
# Remove the extracted directory.
shutil.rmtree(extractdir)
# Remove the archive file and the JSON for the archive.
filepath.unlink()
if filepath_metadata.exists():
    filepath_metadata.unlink()
