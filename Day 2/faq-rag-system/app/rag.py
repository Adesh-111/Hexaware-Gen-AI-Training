import hashlib
import os
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


SYSTEM_PROMPT = """You are a concise employee support assistant for the company.
Answer only from the supplied FAQ context. If the context does not contain the answer, say that you do not have enough information and suggest contacting the AI Platform team.
Keep the answer practical and under 140 words. Do not invent URLs, policies, or capabilities.

FAQ context:
{context}"""


class FAQRAG:
    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.vector_store = None
        self.model = None
        self.ready = False

    def initialize(self):
        persist_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "./data/chroma")
        embeddings = OpenAIEmbeddings(model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"))
        documents = self._load_documents()
        self.vector_store = Chroma.from_documents(
            documents=documents,
            embedding=embeddings,
            collection_name=f"company-faq-{self._source_version()}",
            persist_directory=persist_dir,
            collection_metadata={"hnsw:space": "cosine"},
        )
        self.model = ChatOpenAI(model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"), temperature=0)
        self.ready = True

    def _source_version(self):
        return hashlib.sha256(self.source_path.read_bytes()).hexdigest()[:12]

    def _load_documents(self):
        text = self.source_path.read_text(encoding="utf-8")
        sections = MarkdownHeaderTextSplitter(headers_to_split_on=[("##", "question")]).split_text(text)
        splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=80)
        chunks = splitter.split_documents(sections)
        for index, chunk in enumerate(chunks, start=1):
            chunk.metadata.update({"source": self.source_path.name, "chunk": index})
        return chunks

    def answer(self, question: str):
        results = self.vector_store.similarity_search_with_relevance_scores(question, k=4)
        relevant = [(doc, score) for doc, score in results if score >= 0.25]
        if not relevant:
            return {
                "answer": "I don’t have enough information in the FAQ to answer that. Please contact the AI Platform team for help.",
                "sources": [],
            }

        context = "\n\n".join(
            f"Question: {doc.metadata.get('question', 'FAQ')}\n{doc.page_content}" for doc, _ in relevant
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "{question}"),
        ])
        response = (prompt | self.model).invoke({"context": context, "question": question})
        sources = []
        seen = set()
        for doc, score in relevant:
            title = doc.metadata.get("question", "Company FAQ")
            if title not in seen:
                sources.append({"title": title, "relevance": round(score, 2)})
                seen.add(title)
        return {"answer": response.content, "sources": sources[:3]}
