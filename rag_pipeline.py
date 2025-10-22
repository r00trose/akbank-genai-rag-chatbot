"""
RAG Pipeline - Retrieval Augmented Generation
Vektör veritabanı ve LLM entegrasyonu
"""

import os
from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate

class RAGPipeline:
    """RAG işlemlerini yöneten sınıf"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True,
            timeout=120,
            max_retries=2
        )
        self.vectorstore = None
        self.qa_chain = None
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key='answer'
        )
    
    def create_vectorstore(self, texts: List[str], metadata: List[Dict] = None, persist_directory: str = "./chroma_db"):
        try:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)
            split_texts = []
            for text in texts:
                split_texts.extend(text_splitter.split_text(text))
            if metadata is None:
                metadata = [{"source": "unknown"} for _ in split_texts]
            else:
                expanded_metadata = []
                for i, text in enumerate(texts):
                    splits = text_splitter.split_text(text)
                    expanded_metadata.extend([metadata[i]] * len(splits))
                metadata = expanded_metadata
            self.vectorstore = Chroma.from_texts(texts=split_texts, embedding=self.embeddings, metadatas=metadata, persist_directory=persist_directory)
            self._create_qa_chain()
            print(f"✅ {len(split_texts)} parça vektör veritabanına eklendi")
            return True
        except Exception as e:
            print(f"❌ Vektör veritabanı hatası: {str(e)}")
            return False
    
    def _create_qa_chain(self):
        if self.vectorstore is None:
            raise ValueError("Önce vektör veritabanı oluşturulmalı")
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})
        self.qa_chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm, 
            retriever=retriever, 
            memory=self.memory, 
            return_source_documents=True, 
            verbose=False
        )
    
    def ask_question(self, question: str, language: str = 'tr') -> Dict:
        """Soruyu yanıtla - Dil desteği ile"""
        if self.qa_chain is None:
            return {'answer': "Lütfen önce bir dosya yükleyin.", 'sources': []}
        
        try:
            # Dil bazlı talimatlar
            if language == 'en':
                instruction = """You are a helpful AI assistant. Answer the question based on the provided document context.

Instructions:
- Use bullet points (•) or numbered lists (1. 2. 3.) for clarity
- Use **bold** for important information
- Use ## for section headers if needed
- Provide clear and organized answers
- If you don't know, say "I don't have enough information about this in the document."

Question: """
            else:
                instruction = """Sen yardımsever bir AI asistanısın. Verilen doküman bağlamına göre soruyu yanıtla.

Talimatlar:
- Açıklık için madde işaretleri (•) veya numaralı listeler (1. 2. 3.) kullan
- Önemli bilgiler için **kalın** yazı kullan
- Gerekirse bölüm başlıkları için ## kullan
- Net ve düzenli cevaplar ver
- Bilmiyorsan "Bu konuda dokümanda yeterli bilgi yok." de

Soru: """
            
            # Sadece instruction + soru gönder
            formatted_question = instruction + question
            
            # RAG chain'e sor
            result = self.qa_chain({"question": formatted_question})
            
            return {
                'answer': result['answer'],
                'sources': []
            }
            
        except Exception as e:
            error_msg = "An error occurred: " if language == 'en' else "Hata oluştu: "
            return {
                'answer': f"{error_msg}{str(e)}", 
                'sources': []
            }
    
    def load_vectorstore(self, persist_directory: str = "./chroma_db"):
        try:
            self.vectorstore = Chroma(persist_directory=persist_directory, embedding_function=self.embeddings)
            self._create_qa_chain()
            return True
        except Exception as e:
            print(f"❌ Veritabanı yükleme hatası: {str(e)}")
            return False
    
    def clear_memory(self):
        """Konuşma geçmişini temizle"""
        self.memory.clear()
    
    def generate_summary(self, text: str, max_length: int = 500) -> str:
        """Metin özeti oluştur"""
        if len(text) > 5000:
            text = text[:5000]
        prompt = f"Türkçe özetle (max {max_length} kelime):\n{text}"
        try:
            return self.llm.predict(prompt)
        except Exception as e:
            return f"Özet oluşturulamadı: {str(e)}"