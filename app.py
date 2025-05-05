import streamlit as st
import PyPDF2
import io
import os
import re
import requests
from bs4 import BeautifulSoup
from groq import Groq
from dotenv import load_dotenv
from urllib.parse import urlparse
import random

# Set page config FIRST - must be before any other Streamlit commands
st.set_page_config(
    page_title="AI Resume Customizer", 
    layout="wide",
    page_icon="✨",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Custom CSS for styling
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Create style.css file if it doesn't exist
if not os.path.exists("style.css"):
    css_content = """
    /* Your existing CSS content here */
    """
    with open("style.css", "w") as f:
        f.write(css_content)

# Load custom CSS
local_css("style.css")

# Cool gradient backgrounds
GRADIENTS = [
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
    "linear-gradient(135deg, #6a11cb 0%, #2575fc 100%)",
    "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)"
]

def clean_html(raw_html):
    """Remove HTML tags from a string"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

def get_company_info(url):
    """Scrape company website for basic information"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract basic company info
        company_name = soup.find('title').get_text() if soup.find('title') else urlparse(url).netloc
        description = soup.find('meta', attrs={'name': 'description'})
        description = description['content'] if description else "No description found"
        
        # Try to find about page
        about_link = None
        for link in soup.find_all('a', href=True):
            if 'about' in link['href'].lower():
                about_link = link['href'] if link['href'].startswith('http') else f"{url.rstrip('/')}/{link['href'].lstrip('/')}"
                break
        
        # Get more details from about page if available
        about_text = ""
        if about_link:
            try:
                about_response = requests.get(about_link, headers=headers, timeout=10)
                about_soup = BeautifulSoup(about_response.text, 'html.parser')
                about_text = about_soup.get_text()[:1000] + "..."  # Limit text length
            except:
                about_text = "Could not retrieve additional details"
        
        return {
            "name": clean_html(company_name),
            "description": clean_html(description),
            "about": clean_html(about_text),
            "website": url
        }
    except Exception as e:
        st.error(f"Error scraping company website: {str(e)}")
        return None

# Initialize Groq client
try:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
except Exception as e:
    st.error(f"Failed to initialize Groq client: {str(e)}")
    st.info("Please set your GROQ_API_KEY in the .env file or enter it below")
    api_key = st.text_input("Enter your Groq API key:", type="password")
    if api_key:
        client = Groq(api_key=api_key)
    else:
        st.stop()

def extract_text_from_pdf(uploaded_file):
    """Extract text from uploaded PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
        return "\n".join(page.extract_text() for page in pdf_reader.pages)
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return None

def extract_match_score(analysis_text):
    """Extract the match score percentage from the analysis text."""
    # First try the specific format we requested
    specific_match = re.search(r'## Match Score:\s*(\d+)%', analysis_text)
    if specific_match:
        return int(specific_match.group(1))
    
    # Fallback to more general pattern
    general_match = re.search(r'Match Score.*?(\d+)%', analysis_text)
    if general_match:
        return int(general_match.group(1))
    
    return 0

def analyze_resume_with_groq(jd_text, resume_text, company_info=None):
    """Send JD and resume to Groq API for analysis."""
    company_context = ""
    if company_info:
        company_context = f"""
        Company Context:
        - Name: {company_info['name']}
        - Description: {company_info['description']}
        - About: {company_info['about'][:2000]}
        """
    
    prompt = f"""
    Analyze this job description and resume pair. First, calculate and provide a Match Score between 0-100% 
    based on how well the resume matches the job requirements. Then provide specific, actionable suggestions.
    
    {company_context}

    Job Description:
    {jd_text[:8000]}

    Resume:
    {resume_text[:8000]}

    Provide your analysis with these sections:
    1. Match Score (0-100%) with justification - format exactly as: '## Match Score: X%' where X is the score
    2. Company-Specific Recommendations
    3. Top 3 Missing Keywords
    4. Top 3 Overused Terms
    5. Skills Gap Analysis
    6. Specific Content Improvements
    7. Suggested Action Items

    Format with clear section headers (##) and bullet points. Do not include any HTML tags in your response.
    """
    
    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-70b-8192",
            temperature=0.3,
            max_tokens=4000,
            stream=False
        )
        return clean_html(response.choices[0].message.content)
    except Exception as e:
        return f"API Error: {str(e)}"

def create_placement_indicator(score):
    """Create a visual indicator for placement probability."""
    st.subheader("Resume Match Score")
    
    if score >= 80:
        color = "#4CAF50"  # Green
        emoji = "🎯"
        message = "Excellent match! High probability of getting placed"
        icon = "✨"
    elif score >= 60:
        color = "#8BC34A"  # Light Green
        emoji = "👍"
        message = "Good match - some optimizations could make it perfect"
        icon = "🔍"
    elif score >= 40:
        color = "#FFC107"  # Amber
        emoji = "⚠️"
        message = "Moderate match - needs improvements"
        icon = "📝"
    elif score >= 20:
        color = "#FF9800"  # Orange
        emoji = "🤔"
        message = "Below average - significant improvements needed"
        icon = "🛠️"
    else:
        color = "#F44336"  # Red
        emoji = "❌"
        message = "Poor match - major overhaul required"
        icon = "🚨"
    
    st.markdown(
        f"""
        <div class="score-card" style="border-left: 6px solid {color};">
            <div class="score-header">
                <span class="score-emoji">{emoji}</span>
                <h2 class="score-title">Match Score: {score}%</h2>
                <span class="score-icon">{icon}</span>
            </div>
            <p class="score-message">{message}</p>
            <div class="progress-container">
                <div class="progress-bar" style="width: {score}%; background: {color};">
                    <span class="progress-text">{score}%</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def format_analysis_content(analysis_text):
    """Format the analysis content into styled boxes."""
    # First remove any HTML tags that might have slipped through
    clean_text = clean_html(analysis_text)
    
    # Split into sections
    sections = re.split(r'\n## ', clean_text)
    
    for i, section in enumerate(sections):
        if not section.strip():
            continue
            
        if '\n' in section:
            title, content = section.split('\n', 1)
        else:
            title = section
            content = ""
        
        # Skip the Match Score section since we display it separately
        if "Match Score" in title:
            continue
            
        # Different card styles for different sections
        if "Recommendations" in title:
            card_class = "recommendation-card"
            icon = "💡"
        elif "Missing" in title:
            card_class = "missing-card"
            icon = "🔎"
        elif "Overused" in title:
            card_class = "overused-card"
            icon = "🔄"
        elif "Gap" in title:
            card_class = "gap-card"
            icon = "📉"
        elif "Improvements" in title:
            card_class = "improvement-card"
            icon = "🛠️"
        elif "Action" in title:
            card_class = "action-card"
            icon = "✅"
        else:
            card_class = "default-card"
            icon = "📌"
        
        st.markdown(
            f"""
            <div class="analysis-card {card_class}">
                <div class="card-header">
                    <span class="card-icon">{icon}</span>
                    <h3 class="card-title">{title}</h3>
                </div>
                <div class="card-content">
                    {content.replace('\n', '<br>')}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

def main():
    # Apply random gradient to header
    selected_gradient = random.choice(GRADIENTS)
    
    st.markdown(
        f"""
        <div class="main-header" style="background: {selected_gradient};">
            <h1>✨ AI-Powered Resume Customizer</h1>
            <p class="header-sub">Get company insights and optimize your resume for specific job postings</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Sidebar with info
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <h2>How It Works</h2>
        </div>
        <div class="sidebar-content">
            <div class="step">
                <div class="step-number">1</div>
                <div class="step-content">
                    <h4>Add Company Info</h4>
                    <p>Enter the company URL for tailored recommendations</p>
                </div>
            </div>
            <div class="step">
                <div class="step-number">2</div>
                <div class="step-content">
                    <h4>Upload Documents</h4>
                    <p>Provide the job description and your resume</p>
                </div>
            </div>
            <div class="step">
                <div class="step-number">3</div>
                <div class="step-content">
                    <h4>Get Analysis</h4>
                    <p>Receive personalized optimization suggestions</p>
                </div>
            </div>
        </div>
        <div class="sidebar-footer">
            <p><strong>Tip:</strong> Company info helps us give more targeted advice</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Company Information Section
    with st.expander("🔍 Step 1: Add Company Information (Optional but Recommended)", expanded=True):
        company_url = st.text_input("Enter company website URL:", key="company_url", placeholder="https://www.company.com")
        company_info = None
        
        if company_url:
            with st.spinner("Gathering company information..."):
                company_info = get_company_info(company_url)
                if company_info:
                    st.success(f"Successfully retrieved information for {company_info['name']}")
                    
                    # Display company info in a nice card
                    st.markdown(
                        f"""
                        <div class="company-card">
                            <div class="company-header">
                                <h3>{company_info['name']}</h3>
                                <a href="{company_info['website']}" target="_blank" class="company-link">Visit Website</a>
                            </div>
                            <div class="company-section">
                                <h4>Description</h4>
                                <p>{company_info['description']}</p>
                            </div>
                            <div class="company-section">
                                <h4>About</h4>
                                <p>{company_info['about']}</p>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
    
    # Main analysis section
    st.markdown("""
    <div class="section-header">
        <h2>📄 Step 2: Upload Documents</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center;'>Job Description</h3>", unsafe_allow_html=True)
            jd_file = st.file_uploader("", type="pdf", key="jd_uploader", label_visibility="collapsed")
    
    with col2:
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center;'>Your Resume</h3>", unsafe_allow_html=True)
            resume_file = st.file_uploader("", type="pdf", key="resume_uploader", label_visibility="collapsed")
    
    analyze_button = st.button("🚀 Analyze Documents", use_container_width=True, type="primary")
    
    if analyze_button:
        if jd_file and resume_file:
            with st.spinner("Analyzing your documents... This may take a moment"):
                jd_text = extract_text_from_pdf(jd_file)
                resume_text = extract_text_from_pdf(resume_file)
                
                if jd_text and resume_text:
                    analysis = analyze_resume_with_groq(jd_text, resume_text, company_info)
                    st.session_state.analysis = analysis
                    st.session_state.match_score = extract_match_score(analysis)
                    st.rerun()
                else:
                    st.error("Failed to process one or both documents")
        else:
            st.warning("Please upload both files to proceed")
    
    if "analysis" in st.session_state:
        st.markdown("""
        <div class="section-header">
            <h2>📊 Optimization Report</h2>
        </div>
        """, unsafe_allow_html=True)
        
        create_placement_indicator(st.session_state.match_score)
        format_analysis_content(st.session_state.analysis)
        
        # Add download button with icon
        st.download_button(
            label="📥 Download Full Analysis Report",
            data=st.session_state.analysis,
            file_name="resume_optimization_report.txt",
            mime="text/plain",
            use_container_width=True
        )

if __name__ == "__main__":
    main()