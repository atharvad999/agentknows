#!/usr/bin/env bash
# Regenerate frames/ from the source clip.
#
# Frames only feed a downscaled dither buffer (~200 cells wide at most), so 384px
# is plenty — larger costs payload and buys nothing visible. Keep FRAME_COUNT in
# dither.js in sync with the file count this prints.
set -euo pipefail

SRC="${1:?usage: build-frames.sh <source.mp4>}"
OUT="$(dirname "$0")/frames"

rm -rf "$OUT"
mkdir -p "$OUT"

# fps=11: the dither grid is coarse enough that 24fps buys nothing.
# crop 0.97: trims codec edge artefacts. This source has no painted border; if
# yours does, drop to ~0.84 or the border dithers into a hard rectangle.
ffmpeg -y -v error -i "$SRC" \
  -vf "fps=11,crop=iw*0.97:ih*0.97:iw*0.015:ih*0.015,scale=384:-2" \
  -f image2 -c:v libwebp -lossless 0 -quality 70 -compression_level 6 -vsync 0 \
  "$OUT/%03d.webp"

echo "frames: $(ls "$OUT" | wc -l | tr -d ' ')  size: $(du -sh "$OUT" | cut -f1)"
