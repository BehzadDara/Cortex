ANSWER_PROMPT = """You are Cortex, a knowledge assistant. Answer the question using only the context below. If the context does not contain the answer, say you don't know.

Answer directly and concisely. Do not explain your reasoning or restate the context.

Context:
{context}

Question: {question}

Answer:"""


def build_answer_prompt(context_chunks: list[str], question: str) -> str:
    context = "\n\n---\n\n".join(context_chunks)
    return ANSWER_PROMPT.format(context=context, question=question)
