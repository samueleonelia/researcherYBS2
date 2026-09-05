# Screen one source

You screen **one** news source for one run: you list the stories its front page
is showing today, then read each story's own title and description out of its
page head. You do not read articles and you do not judge them.

## Inputs

- Source: `{{SOURCE_NAME}}` · front page: `{{SOURCE_URL}}`
- Write the result to: `{{RUN_DIR}}/screen/{{SLUG}}.json` (the command does this for you)
- Logged-in marker: `{{MARKER}}` (the literal word `FREE` means the site needs no login)
- Today, local: `{{DATE}}` · window: `{{WINDOW_START}}` to `{{WINDOW_END}}` (UTC)

## Your job

Run the command below **exactly as written**, once. It does everything: opens the
front page in your own task space, collects the links, fetches each link's head
without opening a tab for it, and closes the space. Then reply with the single
line it prints.

```bash
ego-browser nodejs <<'EOF'
const fs = await import('fs')
const OUT = '{{RUN_DIR}}/screen/{{SLUG}}.json'
const t0 = Date.now()
await useOrCreateTaskSpace('ybs screen {{SLUG}}')
await openOrReuseTab('{{SOURCE_URL}}', { wait: true, timeout: 40 })

// 1. Is the session alive? A paid site that has logged us out shows teasers,
//    which look like a thin news day instead of a broken login.
const marker = {{MARKER_JSON}}
if (marker !== 'FREE') {
  const body = await js(String.raw`document.body.innerText`)
  if (!body.includes(marker)) {
    fs.writeFileSync(OUT, JSON.stringify({ source: {{SOURCE_JSON}}, ok: false, error: 'SESSION_DOWN', links: [] }))
    cliLog('{{SOURCE_NAME}}: SESSION_DOWN - the logged-in marker is not on the page')
    await completeTaskSpace('ybs screen {{SLUG}}', { keep: false })
    throw new Error('SESSION_DOWN')
  }
}

// 2. Every article link the front page is showing, with any date the card gives.
const found = await js(String.raw`(() => {
  const host = location.hostname.replace(/^www\./, '')
  const out = new Map()
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href.split('#')[0].split('?')[0]
    if (!href.startsWith('http')) continue
    if (!href.replace(/^https?:\/\/(www\.)?/, '').startsWith(host)) continue
    const path = href.replace(/^https?:\/\/[^/]+/, '')
    if (path.length < 12) continue                 // section hubs, not stories
    const key = href.replace(/\/$/, '')
    if (out.has(key)) continue
    // a date in the url, e.g. /2026/aug/21/ or /2026/08/21/
    const m = path.match(/\/(20\d{2})\/([a-z]{3}|\d{2})\/(\d{2})\//)
    // or a <time datetime> on the card this link sits in
    let stamp = ''
    let n = a
    for (let i = 0; i < 6 && n && !stamp; i++) {
      const t = n.querySelector && n.querySelector('time[datetime], time[dateTime]')
      if (t) stamp = t.getAttribute('datetime') || t.getAttribute('dateTime') || ''
      n = n.parentElement
    }
    out.set(key, {
      url: key,
      card_title: (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 300),
      url_date: m ? m[1] + '-' + m[2] + '-' + m[3] : '',
      card_date: stamp,
    })
  }
  return [...out.values()]
})()`)

// 3. The head of each link: its own title, description, section and timestamp.
//    browserFetch does not render the page and opens no tab, so this is fast.
//    Every <meta> tag is read in ONE pass per page. Scanning the whole page once
//    per tag name with a lazy regex is what made this step time out at first:
//    106 links took over two minutes that way, and six seconds this way.
const ent = s => !s ? '' : s
  .replace(/&#(\d+);/g, (_, d) => String.fromCharCode(+d))
  .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCharCode(parseInt(h, 16)))
  .replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&nbsp;/g, ' ')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim()

const metas = html => {
  const head = html.split(/<\/head>/i)[0] || html.slice(0, 80000)
  const m = {}
  for (const tag of head.match(/<meta\b[^>]*>/gi) || []) {
    const k = (tag.match(/(?:property|name)\s*=\s*["']([^"']+)["']/i) || [])[1]
    const v = (tag.match(/content\s*=\s*["']([^"']*)["']/i) || [])[1]
    if (k && v && !(k.toLowerCase() in m)) m[k.toLowerCase()] = ent(ent(v))   // twice: some sites double-encode
  }
  return m
}
const pick = (m, ...names) => { for (const n of names) if (m[n]) return m[n]; return '' }

// Some sites publish the date as schema.org JSON-LD instead of a meta tag (the
// BBC does). Both are web standards, so read both rather than writing a rule
// for the site.
const ldDate = html => (html.match(/"datePublished"\s*:\s*"([^"]+)"/) || [])[1] || ''

const links = [], errors = []
for (const f of found) {
  try {
    const r = await browserFetch(f.url)
    const h = typeof r === 'string' ? r : (r.body || r.text || '')
    const m = metas(h)
    links.push({
      url: pick(m, 'og:url') || f.url,
      title: pick(m, 'og:title', 'twitter:title') || f.card_title,
      description: pick(m, 'og:description', 'description', 'twitter:description'),
      category: pick(m, 'article:section', 'og:type'),
      published: pick(m, 'article:published_time', 'datepublished')
                 || ldDate(h) || f.card_date || f.url_date || '',
    })
  } catch (e) {
    errors.push({ url: f.url, error: String(e).slice(0, 120) })
  }
}

// Write the result ourselves. It never passes through a reply, so a stray quote
// in a headline cannot corrupt it.
fs.writeFileSync(OUT, JSON.stringify({ source: {{SOURCE_JSON}}, ok: true,
  seconds: Math.round((Date.now() - t0) / 1000), listed: found.length, links, errors }, null, 1))
cliLog(`{{SOURCE_NAME}}: ${found.length} links found, ${links.length} read, ` +
       `${links.filter(l => l.description).length} with a description, ` +
       `${links.filter(l => l.published).length} dated, ${errors.length} errors, ` +
       `${Math.round((Date.now() - t0) / 1000)}s -> ${OUT}`)
await completeTaskSpace('ybs screen {{SLUG}}', { keep: false })
EOF
```

## Output

The command writes the result to disk itself. Reply with **exactly the one line
it printed**, and nothing else: no preamble, no code fence, no commentary.

The data deliberately does not travel through your reply. A headline containing a
quotation mark is enough to corrupt JSON that a model has retyped, and the whole
run reads that file.

If the line says `SESSION_DOWN`, reply with it and stop. Do not retry: a dead
login is for a human to fix.

## Two things worth knowing about the command

`browserFetch` runs from inside the page you have open, so it can only fetch from
**the same site**. That is exactly what this step does, and it is why the front
page must be open before the loop starts. It cannot be used to fetch another
source's pages.

The date is read from three places in order: the `article:published_time` meta
tag, the schema.org `datePublished` field, then any date on the card or in the
URL. Sites use different ones and all of them are standards.

## What you will see, and why it is fine

A front page links to more than articles: author pages, podcast hubs, category
indexes, a subscribe form. They come back with no publication date, or with a
category like `profile` or `website`. Leave them in. Sorting stories from
non-stories is the next step's job, and it is nearly free there; guessing here
would mean writing a rule for every site.

## Hard rules

1. Run the command once, unchanged. Do not edit the JavaScript, do not split it
   into several commands, do not add a second `ego-browser` call.
2. Never open a tab per article. The head fetch is deliberately tab-free; opening
   one tab per link is what made an earlier version of this pipeline unusable.
3. Never read an article, never follow a link out of the front page, never touch
   a second source.
4. Close your task space. The command already does; if it failed before that
   line, close it yourself and say so.
5. If the command errors, reply with the error text as-is. Do not describe it,
   do not guess what went wrong, do not try a different approach.
6. Never write the file yourself and never repeat its contents in your reply. The
   command is the only thing that writes it.
