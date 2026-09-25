# 3xi Atlas media

All media is local under `assets/media`. No remote image, font, music or video host is needed at runtime. These are imagined digital landscapes and motion studies, not travel reportage or field recordings.

## Images

Generated with the built-in image generation tool in new-image mode on 2026-09-25: no reference images, opaque background, 1536×1024 output. PNG masters were converted to WebP with Sharp (quality 88, effort 6). The committed WebP files are the final website assets.

| Asset | Role |
| --- | --- |
| `assets/media/volcanic-coast.webp` | Opening image, coast gallery/film, Low tide cover |
| `assets/media/forest-light.webp` | Main gallery, forest film, vinyl label, Canopy cover |
| `assets/media/quiet-architecture.webp` | Architecture gallery/film, Warm concrete cover |

Creative prompt specifications:

**Volcanic coast:** Photorealistic premium editorial travel-journal hero, remote volcanic coastline with black basalt sand, rust-copper mountains, deep petrol-blue ocean, white surf line, fog around jagged peaks and late-afternoon light. Wide 3:2 landscape composition, tactile film atmosphere. No people, buildings, text, logos or watermarks.

**Forest light:** Photorealistic ancient temperate rainforest, dark trunks, green moss, ferns and a winding path, teal morning mist with a warm shaft of sunlight. Eye-level view, rich tactile film atmosphere, wide 3:2 landscape. No people, text, logos or watermarks.

**Quiet architecture:** Photorealistic modernist terracotta/sandstone courtyard, high arch, monolithic stairs, warm sunlight, long geometric shadows and a still reflecting pool. Architectural editorial composition, wide 3:2 landscape. No people, furniture, text, logos or watermarks.

## Original music

Three original stereo compositions synthesized by [`scripts/build-media.py`](../scripts/build-media.py): `low-tide.mp3` (seed 31), `canopy.mp3` (seed 32), `warm-concrete.mp3` (seed 33). Each score is 64 seconds at 32 kHz before 128 kbit/s MP3 encoding. Container duration includes encoder padding.

Original sine-based pads, bell envelopes, deterministic note/pan choices and a small stereo delay create the scores. No downloaded samples or existing recordings are used.

## Motion studies

`coast.mp4`, `forest.mp4`, `space.mp4`: 16 seconds each, 1280×720, 24 fps, H.264, AAC stereo, yuv420p, faststart. These gently animate the corresponding digital stills with an original soundtrack. They do not depict recorded physical locations.

Rebuild with Python, NumPy and FFmpeg:

```bash
python3 scripts/build-media.py
```

Committed WebP images are inputs; image generation is not repeated. Encoding bytes may differ across FFmpeg versions. All media is prebuilt; the server installer does not run media generation.

## Interaction

Audio/video sources are assigned after a visitor presses play. The playlist advances once started. A film pauses music; closing it releases the video source. Nginx supports byte-range seeking. Saved images, volume and motion preference stay in the browser. No analytics traffic simulation is included.
