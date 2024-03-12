#!/bin/bash

# Check if the number of threads argument is provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <top_folder> <num_threads>"
    exit 1
fi

top_folder="$1"
num_threads="$2"

# Function to process each folder
process_folder() {
    folder="$1"
    echo "Processing folder: $folder"
    poetry run szuru-toolkit upload-media "$folder"
}

# Function to delete empty folders
delete_empty_folders() {
    folder="$1"
    echo "Deleting empty folder: $folder"
    rmdir "$folder"
}

# Export the functions so that they're available to xargs
export -f process_folder
export -f delete_empty_folders

# Find all folders recursively and pass them to xargs
find "$top_folder" -type d | xargs -P "$num_threads" -I {} bash -c 'process_folder "$@"' _ {}
find "$top_folder" -type d -empty | xargs -I {} bash -c 'delete_empty_folders "$@"' _ {}
