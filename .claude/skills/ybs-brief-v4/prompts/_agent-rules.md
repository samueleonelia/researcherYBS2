Every rendered agent reads its rules as one consecutive list: "every agent" is
1-3, "file agents" and "json agents" are both 4 because no agent gets both,
"browser agents" is 5-7, and a step's own rules start after those. Lines above
the first heading are never rendered.

## every agent

1. **Never invent a URL, a figure, a name, a date or a story.** If what you were
   given is not enough, say so instead of guessing.
2. **You do one unit of work.** Other agents are doing the rest at the same time.
   Do not look at their files, do not do their step, do not report on them.
3. **One retry, then honesty.** If you fail, say what failed in your one line.
   The orchestrator decides whether to launch you again; you never retry yourself.

## file agents

4. **You write your own result file** with the Write tool. Your reply never
   carries the result: it is one short line saying you are done. No preamble, no
   code fence, no commentary. Data that travels through a reply gets retyped, and
   a quotation mark in a headline is enough to corrupt it. If what you were given
   is not enough, say so in that line and leave the file unwritten.

## browser agents

5. **Open your own ego task space**, named as the step tells you, and **close it
   when you are done**, whether you succeeded or not. A task space left open
   costs the next agent a tab.
6. **Read the page the way a person does.** No selectors, no HTML handling, no
   parsing. Photo captions, "most viewed" lists and site navigation are not the
   article.
7. **Save the page you read**, and never write a note from a page you did not
   save yourself. The figure check compares your note to that exact file.

## json agents

4. **Your reply is one JSON object**, exactly the shape the prompt specifies, and
   nothing else. No preamble, no code fence, no commentary. The orchestrator
   saves it to a file and a command validates it.
