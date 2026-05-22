import streamlit as st
import requests
import time

API_BASE_URL = "http://127.0.0.1:8080"

st.set_page_config(
    page_title="SAATHI - Legal Aid",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ SAATHI - Voice-First Legal Aid")
st.markdown("*Legal assistance for India's informal workers*")

def check_backend():
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code == 200:
            return True
    except:
        return False
    return False

def check_backend_health():
    st.markdown("---")
    st.subheader("🔍 Backend Status")
    
    if check_backend():
        st.success("✅ Backend is online")
        try:
            response = requests.get(f"{API_BASE_URL}/info", timeout=2)
            if response.status_code == 200:
                info = response.json()
                with st.expander("ℹ️ API Information"):
                    st.json(info)
        except:
            pass
    else:
        st.error("❌ Backend is offline")
        st.info("💡 Start the backend with: `python app/main.py`")
        return False
    
    return True

def main():
    st.markdown("""
    ## 🎯 How to Use
    
    1. **Step 1**: Record your voice complaint in Hindi, Bengali, or Tamil
    2. **Step 2**: Upload supporting evidence (wage slips, contracts, photos)
    3. **Step 3**: Click "Generate Documents" to create your legal notice
    4. **Step 4**: Download your legal notice and case summary
    
    """)
    
    if not check_backend_health():
        return
    
    st.markdown("---")
    
    from ui.components.voice_recorder import record_voice, submit_voice
    from ui.components.file_uploader import upload_evidence, show_evidence_summary
    
    tab1, tab2, tab3 = st.tabs(["🎙️ Record Voice", "📎 Upload Evidence", "📄 Generate Documents"])
    
    with tab1:
        st.header("Step 1: Voice Recording")
        
        audio_bytes, language = record_voice()
        
        if audio_bytes:
            if st.button("🚀 Submit for Transcription", type="primary"):
                session_id = submit_voice(audio_bytes, language)
                if session_id:
                    st.session_state['session_id'] = session_id
                    st.session_state['step1_complete'] = True
                    st.rerun()
    
    with tab2:
        st.header("Step 2: Evidence Upload")
        
        session_id = st.session_state.get('session_id')
        
        if not session_id:
            st.warning("⚠️ Please complete Step 1 (voice recording) first")
        else:
            st.success(f"✅ Session ID: {session_id[:8]}...")
            
            result = upload_evidence(session_id)
            
            if result:
                st.session_state['step2_complete'] = True
                show_evidence_summary()
    
    with tab3:
        st.header("Step 3: Generate Legal Documents")
        
        session_id = st.session_state.get('session_id')
        
        if not session_id:
            st.warning("⚠️ Please complete Step 1 & 2 first")
        else:
            st.info(f"📋 Session ID: {session_id}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Generate Legal Notice & Case Summary", type="primary", use_container_width=True):
                    with st.spinner("🔄 Generating documents..."):
                        try:
                            response = requests.post(
                                f"{API_BASE_URL}/api/generate",
                                json={"session_id": session_id},
                                timeout=10
                            )
                            
                            if response.status_code == 200:
                                st.success("✅ Document generation started!")
                                poll_for_completion(session_id)
                            else:
                                st.error(f"❌ Generation failed: {response.text}")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
            
            with col2:
                if st.button("🔄 Check Status", use_container_width=True):
                    poll_for_completion(session_id)
    
    st.markdown("---")
    st.markdown("""
    ### 📝 Important Notes
    
    - This is a **demo system** for hackathon purposes
    - All AI processing runs **locally** on your computer
    - No data is sent to external servers
    - Generated documents are **drafts** and should be reviewed by a lawyer
    
    ### 🌍 Supported Languages
    
    - 🇮🇳 Hindi (हिंदी)
    - 🇮🇳 Bengali (বাংলা)
    - 🇮🇳 Tamil (தமிழ்)
    
    """)

def poll_for_completion(session_id, interval=3, max_wait=300):
    placeholder = st.empty()
    
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE_URL}/api/status/{session_id}", timeout=5)
            
            if response.status_code == 200:
                status_data = response.json()
                status = status_data.get('status')
                progress = status_data.get('progress', 0)
                current_agent = status_data.get('current_agent', 'Unknown')
                
                if status == 'complete':
                    placeholder.success("🎉 Documents generated successfully!")
                    show_downloads(session_id)
                    return True
                elif status == 'error':
                    placeholder.error("❌ Generation failed. Please try again.")
                    return False
                else:
                    placeholder.info(f"⏳ {current_agent} - {progress}% complete")
                    
                    progress_bar = st.progress(progress / 100.0)
                    status_container = st.empty()
                    
                    with status_container.container():
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Status", status)
                        with col2:
                            st.metric("Progress", f"{progress}%")
                        with col3:
                            st.metric("Agent", current_agent)
                    
                    time.sleep(interval)
                    st.rerun()
            else:
                placeholder.warning(f"⚠️ Status check failed: {response.status_code}")
                break
                
        except Exception as e:
            placeholder.error(f"❌ Error checking status: {str(e)}")
            break
    
    placeholder.warning("⏰ Timeout reached. Please check status manually.")
    return False

def show_downloads(session_id):
    st.success("✅ Documents ready for download!")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            response = requests.get(f"{API_BASE_URL}/api/generate/{session_id}/download/docx", timeout=10)
            if response.status_code == 200:
                st.download_button(
                    "📄 Download Legal Notice (DOCX)",
                    response.content,
                    file_name="legal_notice.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Error downloading DOCX: {e}")
    
    with col2:
        try:
            response = requests.get(f"{API_BASE_URL}/api/generate/{session_id}/download/txt", timeout=10)
            if response.status_code == 200:
                st.download_button(
                    "📝 Download Case Summary (TXT)",
                    response.content,
                    file_name="case_summary.txt",
                    mime="text/plain",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"Error downloading TXT: {e}")
    
    with col3:
        if st.button("🔄 Start New Complaint", use_container_width=True):
            for key in list(st.session_state.keys()):
                if key not in ['step1_complete', 'step2_complete']:
                    del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()
