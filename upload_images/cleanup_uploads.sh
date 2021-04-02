#!/bin/bash

upload_dir=/local/path/to/upload/dir

find ${upload_dir} -type d -name "@eaDir" -print0 | xargs -0 rm -rf
find ${upload_dir} -type f -name "Thumbs.db" -print0 | xargs -0 rm -rf
find ${upload_dir} -type d -print0 | xargs -0 rmdir --ignore-fail-on-non-empty
