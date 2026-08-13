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

Answer no only when the message asks for live or current information (prices, news, weather, sports results), explicitly asks to search the web or look something up online, is pure arithmetic, asks the date or time, asks how many documents, collections, or conversations the library holds, asks about their own usage of this assistant (prompts sent, tokens spent, latency), asks to generate, draw, or create an image or picture, or is small talk — including messages that just tell you what to say back, like greetings, jokes, well-wishes, or canned replies.
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
Message: How many documents are in my library? -> no
Message: How many tokens did I use yesterday? -> no
Message: hey there -> no
Message: Say good morning to me. -> no

Message: {question} ->"""

SUMMARY_PROMPT = """Summarize the conversation below concisely. Keep facts, names, numbers, and user preferences. Output only the summary.

{previous_section}Conversation:
{transcript}

Summary:"""


TRANSCRIBE_PROMPT = """Transcribe all text visible in this image exactly. If the image contains diagrams, charts, or figures, describe each one briefly after the transcription. Output only the transcription and descriptions."""

CAPTION_PROMPT = """Describe this image in one or two sentences so it can be found by search: what it shows, any prominent text, and what it is about. Output only the description."""

def build_title_prompt(question: str) -> str:
    return TITLE_PROMPT.format(question=question)


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
