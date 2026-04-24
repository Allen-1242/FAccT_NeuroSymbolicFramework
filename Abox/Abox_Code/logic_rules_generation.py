import nltk
#nltk.download('punkt_tab')
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.text_rank import TextRankSummarizer

summarizer = TextRankSummarizer()

def summarize_clause(text, sentences_count=1):
    parser = PlaintextParser.from_string(text, Tokenizer("english"))
    summary = summarizer(parser.document, sentences_count)
    return " ".join(str(s) for s in summary) or text


clause = ("Households shall not be required to reside in a permanent dwelling "
          "or have a fixed mailing address as a condition of eligibility. "
          "Nor shall residency require intent to reside permanently in the county.")
#print(summarize_clause(clause))


import ollama, json, re

entry = {
    "summary": "Residency cannot depend on permanent dwelling or fixed mailing address.",
    "concepts": ["Residency:MailingAddress", "Residency:PermanentDwelling", "Eligibility"]
}

prompt = f"""
Clause: {entry['summary']}
Concepts: {', '.join(entry['concepts'])}
Return JSON only, following this example:
{{"hasLogic": "Implies(A,B)", "hasModality": "Definition"}}
Use the provided concept names in place of A and B.
"""

response = ollama.chat(
    model="deepseek-r1:latest",
    messages=[
        {"role": "system", "content": "Return only JSON. No reasoning or <think> text."},
        {"role": "user", "content": prompt}
    ]
)

reply = response["message"]["content"]
clean_reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.DOTALL).strip()

print(clean_reply)



