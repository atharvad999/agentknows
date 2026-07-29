# agentknows landing page

Static page — no build step, no dependencies, no external requests. Serve the
directory and it works:

```bash
python3 -m http.server 8731
```

## Files

| | |
|---|---|
| `index.html` | all copy and markup |
| `styles.css` | palette, type scale, layout, hero scrims |
| `dither.js` | the animated hero |
| `frames/` | 66 WebP frames at 384px, ~1.0 MB total |
| `build-frames.sh` | regenerates `frames/` from a source clip |

## The hero

An ordered-dither renderer over a pre-extracted frame sequence. Each frame is
drawn into an offscreen buffer downscaled so one cell maps to one output dot, so
cost tracks dot count rather than canvas pixels. Per cell: Rec. 709 luma →
auto-levels → gamma → contrast/brightness → floor clamp → 8×8 Bayer quantisation
into `levels` tone steps → a circle whose radius scales with the step. Cells are
bucketed by quantised colour so `fillStyle` is set a few dozen times per frame.

Three things are easy to get wrong and are handled explicitly:

- **Auto-levels are pinned.** Percentiles are computed once at load, across five
  sampled frames and over the same crop the renderer shows. Recomputing per frame
  makes the dot density pulse.
- **The wrap is a crossfade, not a seam.** Flying paper never returns to a prior
  state, so no true loop point exists. Frames `[0, fadeFrames)` are never played
  directly — they fade in over the tail, and playback resumes at `fadeFrames`.
- **The pointer warp displaces sampling coordinates**, not drawn output, so it is
  free per frame. Cells lean away horizontally and lift slightly, matching the
  direction of the falling pages. Radial ripple was deliberately avoided — it
  reads as a lens artefact sitting on top of the image.

### Tuning

Any numeric or boolean key in `CFG` can be overridden from the query string:

```
?bare=1                     hide the scrim and copy, judge the dither alone
?pixelSize=6&levels=6       finer grid, smoother gradation
?zoom=1.2&focusX=0.4        recompose the crop
?invert=1                   flip which tones get the dots
```

`zoom`/`focusX`/`focusY` pick which part of the frame survives the crop. They are
set to keep the bright wall in the source out from behind the headline; the type
sits over the sparser left side.

### Replacing the artwork

```bash
./build-frames.sh /path/to/clip.mp4
```

Then set `FRAME_COUNT` in `dither.js` to the count it prints. The technique needs
a subject made of many small discrete elements — flying pages, a flock, a crowd.
A solid object dithers into an illegible grey blob. The camera must be locked
off; nothing downstream can undo a moving camera.

If the new source is dark on a light background, set `invert: true`.
