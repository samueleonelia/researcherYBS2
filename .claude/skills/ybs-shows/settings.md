# Settings

Every number and name this skill obeys lives here, and nowhere else.

| Setting | Value | What it means |
|---|---|---|
| channel | https://www.youtube.com/@YaronBrook/streams | the page the show list is read from |
| shows_for_profile | 15 | most recent shows the topic profile is built from |
| excluded_titles | "AMA & Hangout", "Yaron & Nikos Dialogues" | a show whose title contains one of these is never used |
| agents_active_max | 10 | agents working at the same time in a pooled step |
| transcript_package | @sinco-lab/mcp-youtube-transcript@0.0.12 | fetches the captions YouTube will not serve any other way; npx downloads it on demand |
| transcript_words_min | 1000 | a transcript shorter than this is not a show; the fetch treats it as no transcript at all |
| list_scrolls_max | 8 | times the list page is scrolled before the listing is taken |
| themes_max_misses | 3 | builds a theme may be absent from before it is dropped from the profile |
| retries_max | 1 | times one agent may be launched again after a failure |
