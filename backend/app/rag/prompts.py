ANSWER_PROMPT = """You are Cortex, a knowledge assistant. Answer the question using only the context below. If the context does not contain the answer, say you don't know.

Answer directly and concisely. Do not explain your reasoning or restate the context.

{history_section}Context:
{context}

Question: {question}

Answer:"""

REWRITE_PROMPT = """Rewrite the follow-up question into a self-contained question that can be understood without the conversation. Keep it short. Output only the rewritten question.

Conversation:
{history}

Follow-up question: {question}

Standalone question:"""

SUMMARY_PROMPT = """Summarize the conversation below concisely. Keep facts, names, numbers, and user preferences. Output only the summary.

{previous_section}Conversation:
{transcript}

Summary:"""


PLAN_PROMPT = """Break the question into at most {max_steps} short search queries that together gather the evidence needed to answer it. Each query must be self-contained and searchable on its own. Output one query per line, nothing else.

Question: {question}

Search queries:"""

SYNTHESIZE_PROMPT = """You are Cortex, a knowledge assistant. Answer the question using only the evidence gathered below. If the evidence is not enough, say you don't know. Answer directly and concisely.

Question: {question}

Evidence:
{evidence}

Answer:"""


def build_plan_prompt(question: str, max_steps: int) -> str:
    return PLAN_PROMPT.format(question=question, max_steps=max_steps)


def build_synthesize_prompt(question: str, evidence: str) -> str:
    return SYNTHESIZE_PROMPT.format(question=question, evidence=evidence)


def build_answer_prompt(
    context_chunks: list[str], question: str, history: str | None = None
) -> str:
    context = "\n\n---\n\n".join(context_chunks)
    history_section = f"Conversation so far:\n{history}\n\n" if history else ""
    return ANSWER_PROMPT.format(
        history_section=history_section, context=context, question=question
    )


def build_rewrite_prompt(history: str, question: str) -> str:
    return REWRITE_PROMPT.format(history=history, question=question)


def build_summary_prompt(previous: str | None, transcript: str) -> str:
    previous_section = f"Previous summary:\n{previous}\n\n" if previous else ""
    return SUMMARY_PROMPT.format(
        previous_section=previous_section, transcript=transcript
    )
