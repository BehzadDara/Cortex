ANSWER_PROMPT = """You are Cortex, a knowledge assistant. Answer the question using only the context below. If the context does not contain the answer, say you don't know.

Answer directly and concisely. Do not explain your reasoning or restate the context.

{history_section}Context:
{context}

Question: {question}

Answer:"""

TITLE_PROMPT = """Write a very short title (3 to 6 words) for a conversation that starts with the message below. Output only the title, without quotes.

Message: {question}

Title:"""

ROUTE_PROMPT = """Decide whether the message should first search the user's personal document library. Output exactly one word: yes or no.

Answer no only when the message asks for live or current information (prices, news, weather, sports results), explicitly asks to search the web or look something up online, is pure arithmetic, asks the date or time, asks how many documents, collections, or conversations the library holds, asks about their own usage of this assistant (prompts sent, tokens spent, latency), asks to generate, draw, or create an image or picture, asks to watch, play, or find a video, or is small talk — including messages that just tell you what to say back, like greetings, jokes, well-wishes, or canned replies.
Otherwise answer yes — general knowledge and how-to questions count as yes, because the documents may cover them.

Message: What is the capital of France? -> yes
Message: How do I brew green tea? -> yes
Message: Explain how our billing service works. -> yes
Message: Tell me what my notes say about tea. -> yes
Message: Reply with the chunk size our backend uses. -> yes
Message: And how about black tea? (follow-up to: Tell me what my notes say about tea.) -> yes
Message: What is the current price of gold? -> no
Message: And for silver? (follow-up to: What is the current price of gold?) -> no
Message: Search the web for the latest Python release. -> no
Message: Who won the match last night? -> no
Message: What is 25 * 16? -> no
Message: Draw a picture of a cat astronaut. -> no
Message: Generate an image of a sunset over the ocean. -> no
Message: Show me a video of how to knead dough. -> no
Message: Can I watch a tutorial video on changing a bike tire? -> no
Message: Now one about pasta. (follow-up to: Show me a video of how to knead dough.) -> no
Message: How many documents are in my library? -> no
Message: How many tokens did I use yesterday? -> no
Message: hey there -> no
Message: Say good morning to me. -> no

Message: {question} ->"""

SUMMARY_PROMPT = """Summarize the conversation below concisely. Keep facts, names, numbers, and user preferences. Output only the summary.

{previous_section}Conversation:
{transcript}

Summary:"""


MEMORY_PROMPT = """Extract durable facts about the user from their message. A durable fact is one that is still true next month: their name, their age, birth date or birthday, where they live or work, their job, the tools and languages they use, their preferences, their health and accessibility needs, and their long-term goals or constraints.

Every fact must name something specific: a name, an age, a date, a place, a job, a tool, a language, a preference, or a condition. Skip anything vague enough to be true of anyone.

Write one fact per line, each a short sentence starting with "The user". Write nothing else. If the message states no durable fact about the user, write exactly: none

Ignore questions, requests, and greetings — including questions the user asks about themselves — and anything that describes the world rather than the user. A question is never a fact, however much it mentions the user. When a message states something about the user and then asks a question, keep the statement and drop the question.

Message: Hi, my name is Behzad and I'm a backend developer.
Facts:
The user is named Behzad.
The user is a backend developer.

Message: What is reciprocal rank fusion?
Facts:
none

Message: I always deploy with Docker Compose, never Kubernetes.
Facts:
The user deploys with Docker Compose rather than Kubernetes.

Message: hey there
Facts:
none

Message: Can you draw me a cat?
Facts:
none

Message: Remind me what my notes say about tea.
Facts:
none

Message: do you know my name? and where do I live?
Facts:
none

Message: What do you remember about me?
Facts:
none

Message: I'm vegetarian, what should I cook tonight?
Facts:
The user is vegetarian.

Message: I deploy things and I work somewhere in tech.
Facts:
none

Message: I'm learning Rust this year because I want to write my own database.
Facts:
The user is learning Rust.
The user wants to write their own database.

Message: The capital of France is Paris.
Facts:
none

Message: I'm colour-blind, so red and green charts are hard for me to read.
Facts:
The user is colour-blind and cannot easily read red and green charts.

Message: {message}
Facts:
"""

SUPERSEDE_PROMPT = """Decide whether the new fact about the user replaces the old fact. Output exactly one word: yes or no.

Answer yes only when both facts describe the same attribute of the user — the same home, job, name, or choice between alternatives — and cannot both be true at once, so keeping the old one would leave a wrong fact stored.
Answer no whenever both can be true together: different attributes, extra detail, or a second item alongside the first. When unsure, answer no.

Old: The user lives in Berlin. New: The user lives in Munich. -> yes
Old: The user is a backend developer. New: The user is a product manager. -> yes
Old: The user deploys with Docker Compose rather than Kubernetes. New: The user deploys with Kubernetes rather than Docker Compose. -> yes
Old: The user is named Behzad. New: The user is named Ali. -> yes
Old: The user is named Behzad. New: The user is a backend developer. -> no
Old: The user lives in Berlin. New: The user works in Munich. -> no
Old: The user is learning Rust. New: The user is learning Go. -> no
Old: The user is colour-blind. New: The user cannot easily read red and green charts. -> no
Old: The user uses Postgres. New: The user uses Postgres 16. -> no
Old: The user prefers dark mode. New: The user prefers tea over coffee. -> no

Old: {old} New: {new} ->"""

TRANSCRIBE_PROMPT = """Transcribe all text visible in this image exactly. If the image contains diagrams, charts, or figures, describe each one briefly after the transcription. Output only the transcription and descriptions."""

CAPTION_PROMPT = """Describe this image in one or two sentences so it can be found by search: what it shows, any prominent text, and what it is about. Output only the description."""

IMAGE_QUESTION_PROMPT = """You are Cortex, looking at an image the user uploaded. You can see and describe the image; you cannot create, edit, or return images, and you have no way to show the user a picture.

If the question asks you to change, edit, recolour, or produce an image, say plainly that you can only describe what you see, then describe the relevant part of the image. Never claim to have edited or generated anything, and never write an image link or markdown image.

Question: {question}

Answer:"""

WEB_PAGE_RULES = """Rules for the page:
- One complete HTML document, starting with <!DOCTYPE html> and ending with </html>, with a <title>.
- All CSS in a single <style> element and all JavaScript in a single <script> element.
- No external resources and no <img> elements: there are no image files, fonts, or scripts to load. Use emoji for icons and pictures and CSS gradients for backgrounds; never draw shapes with hand-written SVG paths.
- Put the content of every header, section, and footer inside a <div class="container">.
- Responsive: looks right from 360px phones to wide desktops.
- Semantic, accessible HTML: headings in order and enough color contrast.
- Realistic copy that fits the request, never lorem ipsum.
- Build every signup, contact, or search box with this pattern, adapting the fields and text:
<form class="signup"><label for="email">Email</label><input id="email" type="email" required placeholder="you@example.com"><button class="btn" type="submit">Subscribe</button></form><p class="form-note" hidden>Thanks, you're on the list!</p>
<script>document.querySelectorAll("form").forEach((form) => form.addEventListener("submit", (event) => { event.preventDefault(); form.hidden = true; form.nextElementSibling.hidden = false; }));</script>
Output only the HTML document, with no explanation before or after it."""

WEB_PAGE_STARTER = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page title</title>
<style>
:root { --bg: #faf7f2; --surface: #ffffff; --text: #2b2118; --muted: #6b5d50; --primary: #8b5e3c; --on-primary: #ffffff; --radius: 16px; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
.container { max-width: 1100px; margin: 0 auto; padding: 0 24px; }
.site-header { position: sticky; top: 0; z-index: 10; background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(8px); border-bottom: 1px solid rgb(0 0 0 / .06); }
.site-header .container { display: flex; align-items: center; justify-content: space-between; height: 68px; }
.brand { font-weight: 800; font-size: 1.25rem; color: var(--text); text-decoration: none; }
.nav { display: flex; gap: 24px; }
.nav a { color: var(--muted); text-decoration: none; font-weight: 500; }
.nav a:hover { color: var(--primary); }
.hero { padding: 120px 0 96px; text-align: center; background: linear-gradient(160deg, color-mix(in srgb, var(--primary) 18%, var(--bg)), var(--bg)); }
.hero .emoji { font-size: 4rem; }
h1 { font-size: clamp(2.4rem, 6vw, 4rem); line-height: 1.1; margin: 16px 0; }
.lead { font-size: 1.2rem; color: var(--muted); max-width: 620px; margin: 0 auto 32px; }
section { padding: 80px 0; }
h2 { font-size: 2rem; margin-bottom: 32px; text-align: center; }
.btn { display: inline-block; padding: 14px 28px; border: 0; border-radius: 999px; background: var(--primary); color: var(--on-primary); font: inherit; font-weight: 600; text-decoration: none; cursor: pointer; transition: transform .15s, box-shadow .15s; }
.btn:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgb(0 0 0 / .15); }
.grid { display: grid; gap: 24px; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); }
.card { background: var(--surface); border-radius: var(--radius); padding: 28px; box-shadow: 0 10px 30px rgb(0 0 0 / .06); }
.card .emoji { font-size: 2.4rem; }
.card h3 { margin: 12px 0 6px; }
.muted { color: var(--muted); }
form { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; }
input, textarea, select { font: inherit; padding: 12px 16px; border: 1px solid #d6cfc7; border-radius: 12px; min-width: 260px; }
.site-footer { padding: 40px 0; text-align: center; color: var(--muted); border-top: 1px solid rgb(0 0 0 / .06); }
@media (max-width: 640px) { .nav { display: none; } section { padding: 56px 0; } }
</style>
</head>
<body>
<header class="site-header"><div class="container"><a class="brand" href="#">Brand</a><nav class="nav"><a href="#first">First</a><a href="#second">Second</a></nav></div></header>
<main>
<section class="hero"><div class="container"><div class="emoji">✨</div><h1>Headline</h1><p class="lead">One supporting sentence.</p><a class="btn" href="#first">Call to action</a></div></section>
<section id="first"><div class="container"><h2>Section title</h2><div class="grid"><article class="card"><div class="emoji">⭐</div><h3>Item</h3><p class="muted">Short description.</p></article></div></div></section>
</main>
<footer class="site-footer"><div class="container"><p>© Brand</p></div></footer>
<script></script>
</body>
</html>"""

WEB_PAGE_PROMPT = """You are an expert front-end developer. Write a single-file web page for this request.

Request: {request}

Build it on the starter page below: keep its structure and classes, recolor the :root variables to fit the request, replace every placeholder with real content, add one section for each thing the request asks for, and extend the CSS for anything new.

Starter page:
{starter}

{rules}"""

WEB_PAGE_EDIT_PROMPT = """You are an expert front-end developer. Here is the current version of a web page you wrote earlier.

Current page:
{html}

{rules}

Change requested by the user: {request}

Apply this change to the page above and output the complete updated document. The change must be clearly visible in the result: returning the page unchanged is wrong. Keep the parts the change does not touch."""


def build_web_page_prompt(request: str, previous_html: str | None = None) -> str:
    if previous_html is None:
        return WEB_PAGE_PROMPT.format(
            request=request, starter=WEB_PAGE_STARTER, rules=WEB_PAGE_RULES
        )
    return WEB_PAGE_EDIT_PROMPT.format(
        request=request, html=previous_html, rules=WEB_PAGE_RULES
    )


def build_title_prompt(question: str) -> str:
    return TITLE_PROMPT.format(question=question)


def build_image_question_prompt(question: str) -> str:
    return IMAGE_QUESTION_PROMPT.format(question=question)


FOLLOW_UP_CONTEXT_CHARS = 200


def build_route_prompt(question: str, previous: str | None = None) -> str:
    message = question
    if previous:
        message = f"{question} (follow-up to: {previous[:FOLLOW_UP_CONTEXT_CHARS]})"
    return ROUTE_PROMPT.format(question=message)


def build_answer_prompt(
    context_chunks: list[str], question: str, history: str | None = None
) -> str:
    context = "\n\n---\n\n".join(context_chunks)
    history_section = f"Conversation so far:\n{history}\n\n" if history else ""
    return ANSWER_PROMPT.format(
        history_section=history_section, context=context, question=question
    )


def build_summary_prompt(previous: str | None, transcript: str) -> str:
    previous_section = f"Previous summary:\n{previous}\n\n" if previous else ""
    return SUMMARY_PROMPT.format(
        previous_section=previous_section, transcript=transcript
    )


def build_memory_prompt(message: str) -> str:
    return MEMORY_PROMPT.format(message=message)


def build_supersede_prompt(old: str, new: str) -> str:
    return SUPERSEDE_PROMPT.format(old=old, new=new)
