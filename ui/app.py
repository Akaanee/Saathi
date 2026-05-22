import streamlit as st

st.set_page_config(
    page_title="SAATHI - Legal Aid",
    page_icon="⚖️",
    layout="wide"
)

def main():
    st.title("⚖️ SAATHI - Voice-First Legal Aid")
    st.markdown("*Legal assistance for India's informal workers*")
    
    st.markdown("""
    ## 🚀 Getting Started
    
    Welcome to **SAATHI** - a voice-first multi-agent legal aid system designed for India's informal workers.
    
    ### Features
    
    - 🎙️ **Voice Recording**: Record your complaint in Hindi, Bengali, or Tamil
    - 📎 **Evidence Upload**: Upload supporting documents (wage slips, contracts, photos)
    - 🤖 **AI-Powered**: Multi-agent AI processes your complaint locally
    - 📄 **Legal Documents**: Generate legal notices and case summaries
    
    ### How It Works
    
    1. Go to **Record Complaint** page (in sidebar)
    2. Record your voice complaint
    3. Upload supporting evidence
    4. Generate legal documents
    
    ### Technical Details
    
    - **100% Local**: All processing happens on your computer
    - **No External APIs**: Zero cost, no data sent to servers
    - **Open Source**: Built with open-source AI models
    
    ### Architecture
    
    - **Whisper**: Speech-to-text for voice recording
    - **Ollama**: Local LLM for AI processing
    - **CrewAI**: Multi-agent orchestration
    - **ChromaDB**: Legal knowledge base
    - **Surya/Tesseract**: OCR for evidence documents
    
    ### Requirements
    
    - Python 3.9+
    - Ollama running locally
    - 16GB RAM (recommended)
    - Models: llama3.1:8b, nomic-embed-text
    
    ---
    
    ### ⚠️ Disclaimer
    
    This is a **demo system** for hackathon purposes.
    
    - Generated documents are **drafts**
    - Should be **reviewed by a qualified lawyer**
    - Not a substitute for **professional legal advice**
    
    """)
    
    st.sidebar.success("Select a page above to get started.")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        ### 🇮🇳 Multi-Language
        Hindi, Bengali, Tamil support
        """)
    
    with col2:
        st.markdown("""
        ### 🔒 Privacy First
        All data stays on your device
        """)
    
    with col3:
        st.markdown("""
        ### 💰 Zero Cost
        No API fees or subscriptions
        """)

if __name__ == "__main__":
    main()
