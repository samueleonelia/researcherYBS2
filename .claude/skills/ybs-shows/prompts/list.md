# List the channel's latest shows

You list what the channel is showing. You open no video, read no transcript and
judge nothing.

Run the command below **exactly as written**, once. It opens the streams page in
your own task space, scrolls it, collects every video's id, title and link,
writes the listing itself, and closes the space.

```bash
ego-browser nodejs <<'EOF'
const fs = await import('fs')
const OUT = '{{SHOWS_DIR}}/new/listing.json'

// Pause with a plain timer, never with the browser's own wait(): that one waits
// for the page to go quiet, and a YouTube channel page never does. It hangs for
// as long as you let it, and nothing downstream ever runs.
const sleep = (ms) => new Promise(r => setTimeout(r, ms))

await useOrCreateTaskSpace('ybs shows list')
// Same reason: { wait: true } would hang on this page. Open, then watch.
await openOrReuseTab('{{CHANNEL}}', { wait: false })

const IDS = String.raw`(() => {
  const s = new Set()
  for (const a of document.querySelectorAll('a[href*="/watch?v="]')) {
    const m = a.href.match(/[?&]v=([A-Za-z0-9_-]{11})/)
    if (m) s.add(m[1])
  }
  return s.size
})()`

for (let i = 0; i < 30; i++) {
  if (await js(IDS) > 0) break
  await sleep(1000)
}

// Streams load a page at a time, and the next page can take a few rounds to
// arrive: this grid sits still twice before it gives up its second page. Stop
// only once three rounds running have brought nothing new.
let seen = await js(IDS), quiet = 0
for (let i = 0; i < {{SCROLLS}}; i++) {
  await scrollBy({ y: 5000 })
  await sleep(2000)
  const n = await js(IDS)
  quiet = (n === seen) ? quiet + 1 : 0
  seen = n
  if (quiet >= 3) break
}

const found = await js(String.raw`(() => {
  // Key on the watch URL, never on class names or element ids: YouTube restyles
  // its grid often, but it cannot change /watch?v=<id> without breaking every
  // link ever made to a video.
  const ID = /[?&]v=([A-Za-z0-9_-]{11})/
  const DURATION = /\s+\d+\s+(hours?|minutes?|seconds?)(,\s*\d+\s+(minutes?|seconds?))*\s*$/i
  const anchors = [...document.querySelectorAll('a[href*="/watch?v="]')]

  // Every video the page is showing, whether or not its title can be read.
  const onPage = new Set()
  for (const a of anchors) {
    const m = a.href.match(ID)
    if (m) onPage.add(m[1])
  }

  const best = new Map()
  for (const a of anchors) {
    const m = a.href.match(ID)
    if (!m) continue
    let text = (a.getAttribute('title') || a.getAttribute('aria-label') ||
                a.textContent || '').replace(/\s+/g, ' ').trim()
    text = text.replace(DURATION, '').trim()
    // A thumbnail anchor carries only the running time; the title anchor and the
    // accessible label carry the words. Keep the wordiest one per video.
    if (!text || /^\d{1,2}:\d{2}(:\d{2})?$/.test(text)) continue
    const prev = best.get(m[1])
    if (prev && prev.title.length >= text.length) continue
    const card = a.closest('ytd-rich-item-renderer, yt-lockup-view-model')
    best.set(m[1], {
      id: m[1],
      title: text,
      url: 'https://www.youtube.com/watch?v=' + m[1],
      meta: ((card && card.innerText) || '').replace(/\s+/g, ' ').trim().slice(0, 200)
    })
  }
  return { videos: [...best.values()], onPage: onPage.size }
})()`)

const { videos, onPage } = found
if (onPage > 0 && videos.length === 0) {
  // The videos are on the page but not one title could be read off them. That is
  // a broken reader, not an empty channel, and it must not look like one.
  cliLog('EXTRACTION_BROKEN 0 of ' + onPage)
} else {
  fs.mkdirSync('{{SHOWS_DIR}}/new', { recursive: true })
  fs.writeFileSync(OUT, JSON.stringify({ channel: '{{CHANNEL}}', videos }, null, 2))
  cliLog(`listed ${videos.length} shows of ${onPage} on the page`)
}
await completeTaskSpace('ybs shows list', { keep: false })
EOF
```

Three outcomes, and you report which one happened:

- `listed <n> shows of <m> on the page` — reply with that line exactly.
- `EXTRACTION_BROKEN 0 of <m>` — the videos rendered but no title could be read
  off them. Reply with that line exactly. Do not run the command again: the
  reader is broken and a second run breaks the same way.
- `listed 0 shows of 0 on the page` — the page never rendered the grid. Reply
  `LIST_EMPTY` and nothing else.

Never try a different page, and never change the command.
