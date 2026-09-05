Field by field:

- `kind` is `"cluster"` when the item has two or more articles, `"single"` when
  it has one. A `"cluster"` with one article is an error.
- `verdict` is on **every** item, cluster or single.
- `profile` is an exact profile name or `null`.
- `read` lists the article ids to read, and every id in it must also be in
  `articles`. For a `DROP`, `read` is empty.
- `why` is one short line. It is read by a person, not by code.
- `near_misses` is where you say which pairs you almost merged and why you did
  not. It is how a human checks your grouping, so do not leave it empty when
  there were genuine near misses.

Code checks the shape, and any of these fails the whole reply:

- **Every article id you were given appears in exactly one item.** An id in two
  items, or in none, fails the whole reply.
- Never invent an id, a name or a profile topic. Never alter one.
- A `read` list may only contain ids from that item's own `articles`.
