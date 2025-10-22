import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv('GOOGLE_API_KEY')

print(f"API Key ilk 10 karakter: {api_key[:10] if api_key else 'BOŞ!'}...")

try:
    genai.configure(api_key=api_key)
    
    # Önce hangi modeller var listele
    print("\n📋 Kullanılabilir modeller:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"  - {m.name}")
    
    # Gemini Pro dene
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
    response = model.generate_content("Merhaba!")
    
    print("\n✅ API KEY ÇALIŞIYOR!")
    print(f"Cevap: {response.text}")
    
except Exception as e:
    print(f"\n❌ HATA: {e}")