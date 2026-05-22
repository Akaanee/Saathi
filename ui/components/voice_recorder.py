import streamlit as st
import requests
import time
from io import BytesIO
import base64

API_BASE_URL = "http://127.0.0.1:8080"

def record_voice():
    st.title("🎙️ Voice Recorder")
    st.markdown("Record your complaint in Hindi, Bengali, or Tamil")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        language = st.selectbox(
            "Select Language",
            options=["hi", "bn", "ta"],
            format_func=lambda x: {"hi": "🇮🇳 Hindi (हिंदी)", "bn": "🇮🇳 Bengali (বাংলা)", "ta": "🇮🇳 Tamil (தமிழ்)"}[x],
            index=0
        )
        
        audio_bytes = st.audio_input("Record your voice complaint")
        
        if audio_bytes:
            st.success("✅ Voice recorded successfully!")
            st.audio(audio_bytes, format="audio/wav")
            
            st.info("💡 **Tip**: Keep your recording clear and include:")
            st.markdown("""
            - Your full name
            - Your address and occupation
            - The respondent's name and details
            - What happened (incident details)
            - When and where it occurred
            - What relief or compensation you seek
            """)
            
            return audio_bytes, language
    
    with col2:
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. Select your language
        2. Click the microphone
        3. Speak clearly in your selected language
        4. Click "Stop" when done
        5. Click 'Submit for Processing'
        """)
    
    return None, None

def submit_voice(audio_bytes, language):
    if not audio_bytes:
        return None
    
    with st.spinner("🔄 Transcribing your voice..."):
        try:
            files = {"audio": ("recording.wav", audio_bytes, "audio/wav")}
            data = {"language": language}
            
            response = requests.post(
                f"{API_BASE_URL}/api/voice",
                files=files,
                data=data,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                st.session_state['session_id'] = result['session_id']
                st.session_state['transcription'] = result['transcription']
                st.session_state['language'] = result['language']
                st.session_state['confidence'] = result['confidence']
                
                st.success("✅ Transcription complete!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Confidence", f"{result['confidence']:.0%}")
                with col2:
                    st.metric("Language", result['language'].upper())
                
                st.subheader("📝 Transcription:")
                st.text_area("Your complaint", result['transcription'], height=150, disabled=True)
                
                return result['session_id']
            else:
                st.error(f"❌ Transcription failed: {response.text}")
                return None
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend. Is the API running on port 8080?")
            return None
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            return None

def check_backend_health():
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            return True
    except:
        return False
    return False
