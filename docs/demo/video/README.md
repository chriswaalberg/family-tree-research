# Workshop demo video

Makes `docs/screenshots/workshop-demo.mp4` and `.gif`: a replica of the Claude desktop app (made-up projects) with the real
Workshop on the right, fed with real events and three versions of the fictional demo tree. Needs Node, `playwright`
(installed anywhere, pointed to with `PW`), Google Chrome and ffmpeg.

```
python3 -I docs/demo/video/make_stages.py /tmp/ftr-video
CHANNEL=chrome PW=<dir>/node_modules/playwright/index.mjs node docs/demo/video/record.mjs /tmp/ftr-video
cp /tmp/ftr-video/workshop-demo.{mp4,gif} docs/screenshots/
MODE=phone CHANNEL=chrome PW=... node docs/demo/video/record.mjs /tmp/ftr-video   # the same timeline on an iPhone
cp /tmp/ftr-video/workshop-phone.{mp4,gif} docs/screenshots/
```

- `make_stages.py`: stage0 without Anna Lindqvist's grandparents, stage1 with them (37 ancestors fly in), stage2 with
  certain links and one rejected.
- `desktop.html`: the app replica (2000×1293); `window.demo` is the API the director calls.
- `phone.html`: an iPhone with the Workshop in Safari (watching over Wi-Fi). Same events and stages, so the same
  Workshop footage; the video starts when the Workshop opens.
- `record.mjs`: the director. Records via Chrome's screencast, sped up `SPEED` times; only for the recording it sets
  the Workshop's `CFG.ONE_BY_ONE` to 4.
