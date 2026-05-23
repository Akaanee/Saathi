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
    
    1. **Step 1**: Record your voice complaint (Auto Detect / Hindi / Bengali / Tamil / English)
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
        
        audio_bytes, language, typed_text = record_voice()
        
        if audio_bytes or (typed_text and typed_text.strip()):
            if st.button("🚀 Submit for Transcription", type="primary"):
                session_id = submit_voice(audio_bytes, language, typed_text=typed_text)
                if session_id:
                    st.session_state['session_id'] = session_id
                    st.session_state['step1_complete'] = True
                    st.rerun()

        if st.session_state.get("session_id") and st.session_state.get("transcription"):
            st.markdown("---")
            st.subheader("📝 Transcription (editable)")
            edited = st.text_area(
                "Edit transcription if needed",
                value=st.session_state.get("transcription", ""),
                height=180,
                key="edited_transcription"
            )
            if st.button("💾 Save Edited Transcription"):
                try:
                    resp = requests.post(
                        f"{API_BASE_URL}/api/status/{st.session_state['session_id']}/transcription",
                        json={"transcription": edited},
                        timeout=10
                    )
                    if resp.status_code == 200:
                        st.session_state["transcription"] = edited
                        st.success("✅ Transcription updated")
                    else:
                        st.error(f"❌ Failed to save transcription: {resp.text}")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
    
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
            st.warning("⚠️ Please complete Step 1 first")
        else:
            st.info(f"📋 Session ID: {session_id}")

            with st.expander("🧠 Improve the case (add missing details / corrections)", expanded=True):
                notes = st.text_area(
                    "Add or correct details (manager name, company, address, dates, amounts, missing evidence description, etc.)",
                    height=140,
                    key="case_notes"
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("💾 Save Notes", use_container_width=True):
                        try:
                            resp = requests.post(
                                f"{API_BASE_URL}/api/status/{session_id}/notes",
                                json={"notes": notes},
                                timeout=10
                            )
                            if resp.status_code == 200:
                                st.success("✅ Notes saved")
                            else:
                                st.error(f"❌ Failed to save notes: {resp.text}")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                with col_b:
                    if st.button("❓ Suggest Missing Info", use_container_width=True):
                        try:
                            if notes and notes.strip():
                                try:
                                    requests.post(
                                        f"{API_BASE_URL}/api/status/{session_id}/notes",
                                        json={"notes": notes},
                                        timeout=10
                                    )
                                except Exception:
                                    pass

                            start = requests.post(
                                f"{API_BASE_URL}/api/status/{session_id}/questions",
                                timeout=10
                            )
                            if start.status_code != 200:
                                st.error(f"❌ Failed to start question generation: {start.text}")
                            else:
                                with st.spinner("Thinking about what might be missing..."):
                                    deadline = time.time() + 120
                                    while time.time() < deadline:
                                        poll = requests.get(
                                            f"{API_BASE_URL}/api/status/{session_id}/questions",
                                            timeout=10
                                        )
                                        if poll.status_code != 200:
                                            st.error(f"❌ Failed to fetch questions: {poll.text}")
                                            break

                                        payload = poll.json()
                                        status = payload.get("status")
                                        if status == "done":
                                            result = payload.get("result") or {}
                                            questions = result.get("questions", [])
                                            missing_fields = result.get("missing_fields", [])
                                            if missing_fields:
                                                st.caption("Missing fields: " + ", ".join([str(x) for x in missing_fields]))

                                            if questions:
                                                st.subheader("Suggested questions")
                                                for q in questions[:8]:
                                                    st.write(f"- {q.get('question')}")
                                                    ex = q.get("example_answer")
                                                    if ex:
                                                        st.caption(f"Example: {ex}")
                                            else:
                                                st.info("No missing info detected.")
                                            break
                                        if status == "error":
                                            st.error(f"❌ Failed to generate questions: {payload.get('error')}")
                                            break

                                        time.sleep(2)
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📄 Generate Legal Notice & Case Summary", type="primary", use_container_width=True):
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
    - 🇬🇧 English
    - 🌐 Auto Detect (best for mixed language)
    
    """)

def poll_for_completion(session_id, interval=3, max_wait=300):
    status_box = st.empty()
    progress_box = st.empty()
    preview_box = st.empty()
    progress_bar = st.progress(0.0)
    
    start_time = time.time()
    
    def render_steps(status: str):
        steps = [
            ("pending", "Session created"),
            ("transcribing", "Voice transcription"),
            ("processing_evidence", "Evidence OCR"),
            ("agents_running", "Agents processing"),
            ("generating_documents", "Document generation"),
            ("complete", "Complete"),
        ]
        
        try:
            current_index = [s[0] for s in steps].index(status)
        except Exception:
            current_index = 0
        
        lines = []
        for i, (_, label) in enumerate(steps):
            mark = "✅" if i < current_index else ("⏳" if i == current_index else "⬜")
            lines.append(f"{mark} {label}")
        return "\n".join(lines)
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{API_BASE_URL}/api/status/{session_id}", timeout=10)
            if response.status_code != 200:
                status_box.warning(f"⚠️ Status check failed: {response.status_code}")
                time.sleep(interval)
                continue
            
            status_data = response.json()
            status = status_data.get('status', 'pending')
            progress = int(status_data.get('progress', 0))
            current_agent = status_data.get('current_agent', 'Unknown')
            preview = status_data.get('output_preview')
            
            status_box.markdown(f"**Current**: {current_agent} | **Status**: {status}")
            progress_bar.progress(min(max(progress / 100.0, 0.0), 1.0))
            progress_box.text(render_steps(status))
            
            if preview:
                preview_box.text(preview)
            
            if status == 'complete':
                status_box.success("🎉 Documents generated successfully!")
                show_downloads(session_id)
                return True
            if status == 'error':
                err = status_data.get("error")
                status_box.error(f"❌ Generation failed{': ' + err if err else ''}")
                return False
            
            time.sleep(interval)
            
        except Exception as e:
            status_box.error(f"❌ Error checking status: {str(e)}")
            return False
    
    status_box.warning("⏰ Timeout reached. Please click 'Check Status'.")
    return False

def show_downloads(session_id):
    st.success("✅ Documents ready for download!")
    
    try:
        docs = requests.get(f"{API_BASE_URL}/api/status/{session_id}/documents", timeout=10)
        if docs.status_code == 200:
            payload = docs.json()
            with st.expander("👀 Preview: Legal Notice"):
                st.text_area("Draft Notice", payload.get("draft_notice", ""), height=280, disabled=True)
            with st.expander("👀 Preview: Case Summary"):
                st.text_area("Case Summary", payload.get("case_summary", ""), height=280, disabled=True)
    except Exception:
        pass
    
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
