import streamlit as st
import requests
import time
from io import BytesIO
import base64
import streamlit.components.v1 as components

API_BASE_URL = "http://127.0.0.1:8080"

def record_voice():
    st.title("🎙️ Voice Recorder")
    st.markdown("Record your complaint (or pick Auto Detect for mixed language)")

    with st.expander("🎤 Microphone permission & input device", expanded=False):
        st.markdown(
            """
If the app doesn't capture audio, it's usually because the browser hasn't been allowed to use your microphone, or the wrong input device is selected.

Steps:
1. Click the microphone widget below and try recording once (this should trigger the browser permission prompt).
2. If you don't see a prompt, open your browser site settings for this page and set Microphone = Allow.
3. Select the correct input device (Built-in mic / Headset mic) in your browser's microphone selector for this site.
4. If permissions are blocked or you're on a locked-down browser, use the "Upload audio file" option instead.
            """.strip()
        )

        if st.button("🔓 Request microphone permission"):
            components.html(
                """
                <div style="font-family: sans-serif;">
                  <button id="req" style="padding: 8px 12px; font-size: 14px;">Request Mic Access</button>
                  <div id="status" style="margin-top: 8px; font-size: 13px;"></div>
                </div>
                <script>
                  const statusEl = document.getElementById('status');
                  document.getElementById('req').addEventListener('click', async () => {
                    try {
                      await navigator.mediaDevices.getUserMedia({ audio: true });
                      statusEl.textContent = "Microphone access granted. You can now use the recorder.";
                    } catch (e) {
                      statusEl.textContent = "Microphone access failed: " + (e && e.message ? e.message : e);
                    }
                  });
                </script>
                """,
                height=120,
            )
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        language = st.selectbox(
            "Select Language",
            options=["auto", "hi", "bn", "ta", "en"],
            format_func=lambda x: {
                "auto": "🌐 Auto Detect (Recommended)",
                "hi": "🇮🇳 Hindi (हिंदी)",
                "bn": "🇮🇳 Bengali (বাংলা)",
                "ta": "🇮🇳 Tamil (தமிழ்)",
                "en": "🇬🇧 English"
            }[x],
            index=0
        )

        input_method = st.radio(
            "Input Method",
            options=["Microphone", "Upload audio file", "Type complaint"],
            horizontal=True
        )

        audio_bytes = None
        typed_text = None
        if input_method == "Microphone":
            audio_bytes = st.audio_input("Record your voice complaint")
        elif input_method == "Upload audio file":
            uploaded_audio = st.file_uploader(
                "Upload an audio file",
                type=["wav", "mp3", "m4a", "webm", "ogg"],
                help="If microphone permission/device selection is problematic, upload an audio recording."
            )
            if uploaded_audio is not None:
                audio_bytes = uploaded_audio.getvalue()
        else:
            typed_text = st.text_area(
                "Type your complaint",
                height=160,
                help="Use this if you can't speak or microphone access is blocked."
            )

        if audio_bytes:
            st.success("✅ Audio ready!")
            try:
                st.audio(audio_bytes)
            except Exception:
                pass

            st.info("💡 **Tip**: Keep your recording clear and include:")
            st.markdown("""
            - Your full name
            - Your address and occupation
            - The respondent's name and details
            - What happened (incident details)
            - When and where it occurred
            - What relief or compensation you seek
            """)

            return audio_bytes, language, None
        if typed_text and typed_text.strip():
            st.success("✅ Text ready!")
            return None, language, typed_text.strip()
        else:
            if input_method == "Microphone":
                st.warning("No audio detected yet. If prompted, allow microphone access and choose the correct input device (built-in mic/headset).")
    
    with col2:
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. Select your language
        2. Choose Microphone or Upload
        3. If using microphone, allow browser permission and select the right input device
        3. Speak clearly in your selected language
        4. Click "Stop" when done
        5. Click 'Submit for Processing'
        """)
    
    return None, None, None

def submit_voice(audio_bytes, language, typed_text=None):
    if not audio_bytes and not (typed_text and typed_text.strip()):
        return None
    
    spinner_text = "🔄 Processing..."
    if typed_text and typed_text.strip():
        spinner_text = "🔄 Saving typed complaint..."
    else:
        spinner_text = "🔄 Transcribing your voice..."

    with st.spinner(spinner_text):
        try:
            if typed_text and typed_text.strip():
                response = requests.post(
                    f"{API_BASE_URL}/api/voice/text",
                    data={"language": language, "transcription": typed_text},
                    timeout=30
                )
            else:
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
