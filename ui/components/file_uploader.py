import streamlit as st
import requests

API_BASE_URL = "http://127.0.0.1:8080"

def upload_evidence(session_id):
    st.subheader("📎 Upload Evidence")
    st.markdown("Upload images of supporting documents (wage slips, contracts, photos, etc.)")
    
    uploaded_files = st.file_uploader(
        "Choose image files",
        type=['jpg', 'jpeg', 'png', 'webp'],
        accept_multiple_files=True,
        help="Upload clear images of supporting documents. Max 10 files, 10MB each."
    )
    
    if uploaded_files:
        st.info(f"📁 {len(uploaded_files)} file(s) selected")
        
        with st.expander("📋 Preview uploaded files"):
            for i, file in enumerate(uploaded_files[:5]):
                st.image(file, caption=f"File {i+1}: {file.name}", width=200)
            
            if len(uploaded_files) > 5:
                st.info(f"... and {len(uploaded_files) - 5} more files")
        
        if st.button("🚀 Process Evidence", type="primary"):
            return process_evidence(uploaded_files, session_id)

    st.markdown("---")
    st.subheader("📝 Add Manual Evidence Text")
    manual_text = st.text_area(
        "If OCR fails, paste the text from the document here (or type key details).",
        height=140,
        key="manual_evidence_text"
    )
    manual_filename = st.text_input("Label", value="manual_evidence.txt", key="manual_evidence_filename")
    if st.button("➕ Add Manual Evidence", use_container_width=True):
        if not manual_text.strip():
            st.warning("⚠️ Manual evidence text is empty")
        else:
            try:
                response = requests.post(
                    f"{API_BASE_URL}/api/evidence/manual",
                    data={"session_id": session_id, "text": manual_text, "filename": manual_filename},
                    timeout=20
                )
                if response.status_code == 200:
                    result = response.json()
                    extracted_texts = st.session_state.get('extracted_texts', [])
                    extracted_texts.extend(result.get("extracted_texts", []))
                    st.session_state['extracted_texts'] = extracted_texts
                    st.session_state['evidence_count'] = len(extracted_texts)
                    st.success("✅ Manual evidence added")
                    show_evidence_summary()
                else:
                    st.error(f"❌ Failed to add manual evidence: {response.text}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    return None

def process_evidence(uploaded_files, session_id):
    if not uploaded_files:
        return None
    
    if not session_id:
        st.error("❌ Please submit voice recording first")
        return None
    
    with st.spinner(f"🔄 Processing {len(uploaded_files)} evidence file(s)..."):
        try:
            files = [("files", (f.name, f.getvalue(), f.type)) for f in uploaded_files]
            
            response = requests.post(
                f"{API_BASE_URL}/api/evidence",
                files=files,
                data={"session_id": session_id},
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                processing_time = result.get('processing_time', 0)
                
                st.success(f"✅ Evidence processed in {processing_time:.1f} seconds!")
                
                extracted_texts = result.get('extracted_texts', [])
                st.session_state['evidence_count'] = len(extracted_texts)
                st.session_state['extracted_texts'] = extracted_texts
                
                st.subheader("📝 Extracted Text from Evidence:")
                
                for i, evidence in enumerate(extracted_texts):
                    with st.expander(f"📄 Evidence {i+1}: {evidence.get('filename', 'Unknown')}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Confidence", f"{evidence.get('confidence', 0):.0%}")
                        with col2:
                            st.metric("Words", evidence.get('word_count', 0))
                        
                        st.text_area(
                            "Extracted Text",
                            evidence.get('text', 'No text extracted'),
                            height=100,
                            disabled=True,
                            key=f"evidence_{i}"
                        )
                
                return result
            else:
                st.error(f"❌ Evidence processing failed: {response.text}")
                st.info("💡 If OCR is not available, use the 'Add Manual Evidence Text' section below.")
                return None
                
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend. Is the API running on port 8080?")
            return None
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            return None

def show_evidence_summary():
    if st.session_state.get('extracted_texts'):
        extracted = st.session_state['extracted_texts']
        total_words = sum(e.get('word_count', 0) for e in extracted)
        avg_confidence = sum(e.get('confidence', 0) for e in extracted) / len(extracted) if extracted else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Files Processed", len(extracted))
        with col2:
            st.metric("Total Words", total_words)
        with col3:
            st.metric("Avg Confidence", f"{avg_confidence:.0%}")
