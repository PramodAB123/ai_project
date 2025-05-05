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

# Set page config with a more modern theme
st.set_page_config(
    page_title="AI Resume Customizer",
    layout="wide",
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Custom CSS for modern styling
st.markdown("""
<style>
    /* Modern color scheme */
    :root {
        --primary-color: #4F46E5;
        --secondary-color: #818CF8;
        --accent-color: #C7D2FE;
        --background-color: #F8FAFC;
        --text-color: #1E293B;
    }

    /* Main container styling */
    .main {
        background-color: var(--background-color);
        padding: 2rem;
    }

    /* Header styling */
    .header {
        background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
        padding: 3rem 2rem;
        border-radius: 1rem;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .header h1 {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        font-weight: 700;
    }

    .header p {
        font-size: 1.2rem;
        opacity: 0.9;
    }

    /* Card styling */
    .card {
        background: white;
        border-radius: 1rem;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s ease;
    }

    .card:hover {
        transform: translateY(-2px);
    }

    /* Button styling */
    .stButton>button {
        background: var(--primary-color);
        color: white;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        border: none;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton>button:hover {
        background: var(--secondary-color);
        transform: translateY(-1px);
    }

    /* File uploader styling */
    .stFileUploader {
        border: 2px dashed var(--accent-color);
        border-radius: 0.5rem;
        padding: 1rem;
    }

    /* Progress bar styling */
    .progress-bar {
        background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
        border-radius: 1rem;
        height: 0.5rem;
    }

    /* Sidebar styling */
    .css-1d391kg {
        background-color: white;
    }

    .sidebar-header {
        padding: 1rem;
        border-bottom: 1px solid var(--accent-color);
    }

    /* Animation classes */
    .fade-in {
        animation: fadeIn 0.5s ease-in;
    }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Responsive design */
    @media (max-width: 768px) {
        .header {
            padding: 2rem 1rem;
        }
        
        .header h1 {
            font-size: 2rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Cool gradient backgrounds
GRADIENTS = [
    "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    "linear-gradient(135deg, #6a11cb 0%, #2575fc 100%)",
    "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
    "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)"
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
    client = Groq(api_key=os.environ.get("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"))
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
        color = "#10b981"  # Green
        emoji = "🎯"
        message = "Excellent match! High probability of getting placed"
        icon = "✨"
    elif score >= 60:
        color = "#84cc16"  # Light Green
        emoji = "👍"
        message = "Good match - some optimizations could make it perfect"
        icon = "🔍"
    elif score >= 40:
        color = "#f59e0b"  # Amber
        emoji = "⚠️"
        message = "Moderate match - needs improvements"
        icon = "📝"
    elif score >= 20:
        color = "#f97316"  # Orange
        emoji = "🤔"
        message = "Below average - significant improvements needed"
        icon = "🛠️"
    else:
        color = "#ef4444"  # Red
        emoji = "❌"
        message = "Poor match - major overhaul required"
        icon = "🚨"
    
    st.markdown(
        f"""
        <div class="score-card">
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
            card_class = "analysis-card"
            icon = "📌"
        
        st.markdown(
            f"""
            <div class="{card_class}">
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
    # Header section
    st.markdown("""
    <div class="header fade-in">
        <h1>🎯 AI Resume Optimizer</h1>
        <p>Optimize your resume for your dream job with AI-powered insights</p>
    </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-header">
            <h2>How It Works</h2>
        </div>
        """, unsafe_allow_html=True)
        
        steps = [
            ("1", "Upload Resume", "Upload your current resume in PDF format"),
            ("2", "Add Job Description", "Paste or upload the job description you're targeting"),
            ("3", "Get Insights", "Receive AI-powered optimization suggestions")
        ]
        
        for num, title, desc in steps:
            st.markdown(f"""
            <div class="card fade-in">
                <h3>Step {num}: {title}</h3>
                <p>{desc}</p>
            </div>
            """, unsafe_allow_html=True)

    # Main content area
    col1, col2 = st.columns([2, 1])

    with col1:
        # Resume upload section
        st.markdown("""
        <div class="card fade-in">
            <h2>📄 Upload Your Resume</h2>
        </div>
        """, unsafe_allow_html=True)
        
        resume_file = st.file_uploader("Choose your resume (PDF)", type="pdf", key="resume")

        # Job description section
        st.markdown("""
        <div class="card fade-in">
            <h2>🎯 Job Description</h2>
        </div>
        """, unsafe_allow_html=True)
        
        jd_option = st.radio("Choose input method:", ["Upload PDF", "Paste Text"])
        
        if jd_option == "Upload PDF":
            jd_file = st.file_uploader("Upload job description (PDF)", type="pdf", key="jd")
        else:
            jd_text = st.text_area("Paste job description here", height=200)

    with col2:
        # Additional options
        st.markdown("""
        <div class="card fade-in">
            <h2>⚙️ Options</h2>
        </div>
        """, unsafe_allow_html=True)
        
        analysis_depth = st.select_slider(
            "Analysis Depth",
            options=["Basic", "Standard", "Detailed"],
            value="Standard"
        )
        
        include_keywords = st.checkbox("Include keyword analysis", value=True)
        include_skills = st.checkbox("Include skills gap analysis", value=True)
        include_formatting = st.checkbox("Include formatting suggestions", value=True)

    # Analysis button
    if st.button("🚀 Analyze Resume", use_container_width=True):
        with st.spinner("Analyzing your resume..."):
            # Placeholder for analysis logic
            st.success("Analysis complete!")
            
            # Display results in an expandable section
            with st.expander("View Analysis Results", expanded=True):
                st.markdown("""
                <div class="card fade-in">
                    <h2>📊 Analysis Results</h2>
                </div>
                """, unsafe_allow_html=True)
                
                # Match score
                st.markdown("""
                <div class="card fade-in">
                    <h3>Match Score</h3>
                    <div class="progress-bar" style="width: 75%;"></div>
                    <p>75% match with job requirements</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Recommendations
                st.markdown("""
                <div class="card fade-in">
                    <h3>Key Recommendations</h3>
                    <ul>
                        <li>Add more quantifiable achievements</li>
                        <li>Highlight relevant technical skills</li>
                        <li>Optimize for ATS compatibility</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
