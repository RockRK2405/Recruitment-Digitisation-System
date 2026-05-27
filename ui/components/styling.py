import streamlit as st

def inject_premium_styles():
    """Injects high-fidelity custom CSS into Streamlit for a premium industrial design system."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
        
        <style>
            /* Base Typography Overrides */
            html, body, [class*="css"] {
                font-family: 'Inter', sans-serif;
            }
            h1, h2, h3, h4, h5, h6 {
                font-family: 'Outfit', sans-serif;
                font-weight: 600;
                letter-spacing: -0.02em;
            }
            
            /* Gradient Header Effect */
            .gradient-title {
                background: linear-gradient(135deg, #ffd700 0%, #ff8c00 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                font-size: 2.8rem;
                font-weight: 700;
                margin-bottom: 0.2rem;
            }
            .gradient-subtitle {
                color: #8f9bb3;
                font-size: 1.1rem;
                font-weight: 400;
                margin-bottom: 2rem;
            }
            
            /* Premium Glassmorphism Cards */
            .glass-card {
                background: rgba(22, 26, 32, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 12px;
                padding: 1.5rem;
                margin-bottom: 1rem;
                box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
                transition: all 0.3s ease-in-out;
            }
            .glass-card:hover {
                transform: translateY(-4px);
                border-color: rgba(255, 140, 0, 0.4);
                box-shadow: 0 12px 40px 0 rgba(255, 140, 0, 0.15);
            }
            
            /* Metric Grid Widgets */
            .metric-val {
                font-size: 2rem;
                font-weight: 700;
                color: #ffffff;
                margin-top: 0.5rem;
            }
            
            /* Custom Status Badges */
            .badge {
                display: inline-block;
                padding: 0.25em 0.6em;
                font-size: 75%;
                font-weight: 600;
                line-height: 1;
                text-align: center;
                white-space: nowrap;
                vertical-align: baseline;
                border-radius: 0.375rem;
                margin-right: 0.5rem;
            }
            .badge-verified {
                background-color: rgba(0, 230, 118, 0.15);
                color: #00e676;
                border: 1px solid rgba(0, 230, 118, 0.3);
            }
            .badge-warning {
                background-color: rgba(255, 234, 0, 0.15);
                color: #ffea00;
                border: 1px solid rgba(255, 234, 0, 0.3);
            }
            .badge-low-literacy {
                background-color: rgba(0, 176, 255, 0.15);
                color: #00b0ff;
                border: 1px solid rgba(0, 176, 255, 0.3);
            }
            .badge-failed {
                background-color: rgba(255, 23, 68, 0.15);
                color: #ff1744;
                border: 1px solid rgba(255, 23, 68, 0.3);
            }

            /* Custom Progress Pipeline Indicator for Agent flow */
            .pipeline-step {
                background: #1e222b;
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 0.5rem;
                border-left: 4px solid #ffd700;
            }
            .pipeline-step.completed {
                border-left-color: #00e676;
            }
            .pipeline-step.failed {
                border-left-color: #ff1744;
            }
            
            /* Streamlit specific widget customizations */
            .stButton>button {
                background: linear-gradient(135deg, #ffd700 0%, #ff8c00 100%) !important;
                color: #000000 !important;
                font-weight: 600 !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 0.5rem 2rem !important;
                transition: all 0.3s !important;
            }
            .stButton>button:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 6px 20px rgba(255, 140, 0, 0.4) !important;
            }
            
            /* Sidebar glass pane styling */
            [data-testid="stSidebar"] {
                background-color: #0c0e12 !important;
                border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
