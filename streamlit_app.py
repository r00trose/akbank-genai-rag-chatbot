import streamlit as st
import os
import io
from pathlib import Path
from dotenv import load_dotenv
from rag_pipeline import RAGPipeline
from document_processor import DocumentProcessor

# .env dosyasını yükle (yerel çalıştırma için)
load_dotenv()

# Streamlit sayfa ayarları
st.set_page_config(page_title="ASKRAG Chatbot", layout="wide", initial_sidebar_state="expanded")
st.title("📚 ASKRAG Chatbot - Belgelerinizle Sohbet Edin")

# --- CSS Stilleri (Görünümü güzelleştirmek için) ---
st.markdown("""
<style>
    .reportview-container {
        background: #0e1117;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .css-1d391kg {
        padding-top: 3.5rem;
    }
    /* Streamlit Chat Mesajlarını Özelleştirme */
    .st-emotion-cache-1c7v0s0 p {
        font-size: 16px;
        line-height: 1.6;
    }
    /* AI Mesaj Arka Planı */
    [data-testid="stChatMessage"][data-testid^="stChatMessage_"] {
        background-color: #1e2130; 
        border-radius: 12px;
        padding: 15px;
    }
    /* Kullanıcı Mesaj Arka Planı */
    [data-testid="stChatMessage"][data-testid^="stChatMessage_"] {
        background-color: #1e2130; 
        border-radius: 12px;
        padding: 15px;
        border: 1px solid #333642;
    }
    /* AI icon rengi */
    .st-emotion-cache-1v0k0u4 {
        background-color: #1a4dff; 
        color: white;
    }
    /* Markdown Format Düzeltmeleri */
    .st-emotion-cache-1c7v0s0 pre {
        background-color: rgba(255, 255, 255, 0.05); 
        border-left: 3px solid #1a4dff;
    }
    .st-emotion-cache-1c7v0s0 h1, .st-emotion-cache-1c7v0s0 h2, .st-emotion-cache-1c7v0s0 h3 {
        color: #1a4dff;
        margin-top: 15px;
    }
    .st-emotion-cache-1c7v0s0 strong {
        color: #8aa3ff;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)
# -----------------------------------------------

# Session State başlatma
if "pipeline" not in st.session_state:
    # API key kontrolü
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        st.error("Lütfen GOOGLE_API_KEY ortam değişkenini ayarlayın!")
        st.session_state.pipeline = None
    else:
        st.session_state.pipeline = RAGPipeline(api_key=api_key)
        
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "doc_processor" not in st.session_state:
    st.session_state.doc_processor = DocumentProcessor(
        doc_dir="static/uploads", 
        db_dir="chroma_db", 
        api_key=os.getenv("GOOGLE_API_KEY")
    )
    
if "db_initialized" not in st.session_state:
    st.session_state.db_initialized = False

# --- Fonksiyonlar ---
def process_uploaded_files(uploaded_files):
    """Yüklenen dosyaları işler, kaydeder ve DB'yi günceller."""
    if not st.session_state.pipeline:
        st.error("RAG Pipeline başlatılamadı (API Key eksik).")
        return
    
    # Geçici kaydetme ve işleme
    files_to_process = []
    
    # 1. Yüklenen dosyaları kaydetme
    for uploaded_file in uploaded_files:
        try:
            # Dosya içeriğini byte olarak oku
            file_bytes = uploaded_file.getvalue()
            
            # Geçici olarak diske kaydet (DocumentProcessor'ın ihtiyacı olabilir)
            temp_path = Path("static/uploads") / uploaded_file.name
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            
            files_to_process.append(str(temp_path))
            
        except Exception as e:
            st.error(f"Dosya işlenirken hata oluştu ({uploaded_file.name}): {e}")
            return

    if not files_to_process:
        st.warning("İşlenecek dosya bulunamadı.")
        return

    # 2. DocumentProcessor ile belgeleri işleme ve DB'yi güncelleme
    with st.spinner(f"{len(files_to_process)} adet belge işleniyor ve veritabanı güncelleniyor..."):
        try:
            st.session_state.doc_processor.process_documents_and_save_db(files_to_process)
            st.success(f"Başarılı! {len(files_to_process)} adet belge işlendi ve veritabanı güncellendi.")
            st.session_state.db_initialized = True
            
            # Chat geçmişini sıfırla (yeni bağlam eklendiği için)
            st.session_state.messages = [{"role": "assistant", "content": "Veritabanı güncellendi. Belgelerinizle ilgili sorunuzu sorabilirsiniz."}]

        except Exception as e:
            st.error(f"Belgeler işlenirken kritik hata: {e}")
            # Hata durumunda yüklenen dosyaları sil
            for f_path in files_to_process:
                Path(f_path).unlink(missing_ok=True)


def handle_user_query(user_query):
    """Kullanıcı sorgusunu RAG pipeline'a gönderir ve cevabı işler."""
    if not st.session_state.pipeline or not st.session_state.db_initialized:
        st.session_state.messages.append({"role": "assistant", "content": "Lütfen önce belge yükleyin ve veritabanının güncellenmesini bekleyin."})
        return

    # Kullanıcı mesajını ekle
    st.session_state.messages.append({"role": "user", "content": user_query})

    # Chat'i güncelle (kullanıcının mesajı hemen görünsün)
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.spinner("Cevap aranıyor..."):
        try:
            # RAGPipeline'dan cevap al
            response_text = st.session_state.pipeline.ask_question(
                query=user_query, 
                language="Türkçe"  # Dili sabit Türkçe/İngilizce olarak ayarla
            )
            
            # Bot cevabını ekle
            st.session_state.messages.append({"role": "assistant", "content": response_text})

        except Exception as e:
            error_message = f"Cevap alınırken bir hata oluştu: {e}"
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            response_text = error_message

    # Chat'i güncelle (bot mesajı görünsün)
    with st.chat_message("assistant"):
        st.markdown(response_text)


# --- Streamlit Arayüzü ---

# Sol Kenar Çubuğu (Sidebar)
with st.sidebar:
    st.header("Upload/Yükleme 📁")
    st.markdown("PDF, DOCX, PPTX veya TXT dosyalarınızı yükleyin. Belgeleriniz işlenip veritabanına eklenecektir.")

    uploaded_files = st.file_uploader(
        "Belge Yükle",
        type=["pdf", "docx", "txt", "pptx"],
        accept_multiple_files=True,
        help="Birden fazla dosya yükleyebilirsiniz."
    )
    
    if st.button("Belgeleri İşle ve Veritabanını Güncelle", type="primary"):
        if uploaded_files:
            process_uploaded_files(uploaded_files)
        else:
            st.warning("Lütfen önce bir veya birden fazla dosya seçin.")

    st.markdown("---")
    st.info("⚠️ **GOOGLE_API_KEY** Ortam değişkeni ayarlanmalıdır.", icon="ℹ️")
    st.markdown("Bootcamp Projesi için: **r00trose**")


# Ana Chat Alanı

# Veritabanı başlangıç durumu kontrolü
if not st.session_state.db_initialized:
    # Eğer db_initialized False ise, veritabanı dosyasının varlığını kontrol et (eğer daha önce oluşturulduysa)
    db_path = Path("chroma_db")
    if db_path.exists() and any(db_path.iterdir()):
        st.session_state.db_initialized = True
        if not st.session_state.messages:
            st.session_state.messages.append({"role": "assistant", "content": "Veritabanı daha önce oluşturulmuş. Sorunuzu sorabilirsiniz."})
    elif not st.session_state.messages:
        # İlk karşılama mesajı
        st.session_state.messages.append({"role": "assistant", "content": "Merhaba! Ben ASKRAG Chatbot. Lütfen soldaki menüden belgelerinizi yükleyin ve veritabanını güncelleyin."})


# Geçmiş mesajları görüntüle
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # st.markdown Streamlit'in yerleşik markdown desteğini kullanır, 
        # bu da HTML arayüzünde gördüğümüz formatlamayı otomatik yapar.
        st.markdown(message["content"])

# Kullanıcı girişi
user_query = st.chat_input("Belgelerinizle ilgili sorunuzu buraya yazın...")
if user_query:
    handle_user_query(user_query)