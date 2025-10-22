"""
Akbank GenAI Bootcamp - RAG Chatbot
Flask Web Application
"""

import os
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from document_processor import DocumentProcessor
from rag_pipeline import RAGPipeline
import secrets

# Ortam değişkenlerini yükle
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt', 'pptx'}

# Global değişkenler
doc_processor = DocumentProcessor()
rag_pipeline = RAGPipeline(api_key=os.getenv('GOOGLE_API_KEY'))

def allowed_file(filename):
    """Dosya uzantısı kontrolü"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Dosya yükleme endpoint'i
    Desteklenen formatlar: PDF, DOCX, TXT, PPTX
    """
    try:
        # Dosya kontrolü
        if 'file' not in request.files:
            return jsonify({'error': 'Dosya bulunamadı'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'Dosya seçilmedi'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Desteklenmeyen dosya formatı'}), 400
        
        # Dosyayı kaydet
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(filepath)
        
        # Dosyayı işle
        result = doc_processor.extract_text(filepath)
        text = result['text']
        metadata = result['metadata']
        
        # Vektör veritabanı oluştur
        chunks = doc_processor.chunk_text(text)
        success = rag_pipeline.create_vectorstore(
            texts=chunks,
            metadata=[metadata] * len(chunks)
        )
        
        if not success:
            return jsonify({'error': 'Vektör veritabanı oluşturulamadı'}), 500
        
        # Session'a dosya bilgisini kaydet
        session['current_file'] = filename
        session['file_metadata'] = metadata
        
        # Dosyayı sil (güvenlik için)
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'file_type': metadata['file_type'],
            'page_count': result['page_count'],
            'message': f'{filename} başarıyla yüklendi! Şimdi sorular sorabilirsiniz.'
        })
        
    except Exception as e:
        return jsonify({'error': f'Dosya işleme hatası: {str(e)}'}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Soru sorma endpoint'i"""
    try:
        data = request.get_json()
        question = data.get('question', '')
        language = data.get('language', 'tr')  # ✅ Dil parametresi eklendi
        
        if not question:
            return jsonify({'error': 'Soru boş olamaz'}), 400
        
        # Dosya yüklenmiş mi kontrol et
        if 'current_file' not in session:
            return jsonify({
                'error': 'Lütfen önce bir dosya yükleyin'
            }), 400
        
        # Soruyu yanıtla (dil parametresi ile)
        result = rag_pipeline.ask_question(question, language=language)  # ✅ Language parametresi eklendi
        
        return jsonify({
            'answer': result['answer'],
            'sources': result['sources']
        })
        
    except Exception as e:
        return jsonify({'error': f'Soru yanıtlama hatası: {str(e)}'}), 500

@app.route('/clear', methods=['POST'])
def clear_session():
    """Konuşma geçmişini temizle"""
    try:
        rag_pipeline.clear_memory()
        session.clear()
        
        return jsonify({
            'success': True,
            'message': 'Konuşma geçmişi temizlendi'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Sistem sağlık kontrolü"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0',
        'supported_formats': list(app.config['ALLOWED_EXTENSIONS'])
    })

if __name__ == '__main__':
    # Gerekli klasörleri oluştur
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('./chroma_db', exist_ok=True)
    
    # Uygulamayı başlat
    # Render için PORT environment variable kullan
    port = int(os.environ.get('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)