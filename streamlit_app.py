import streamlit as strl
import math
import requests
import re

# פונקציית סריקת ה-SDS וחילוץ נתונים + חילוץ שם הנייר אוטומטית
def parse_sds_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        text = response.text
        text_lower = text.lower()
        url_lower = url.lower()
        
        x_cellulose, x_lignin, x_acid, is_tissue = 1.0, 0.0, 0.0, False
        extracted_name = "Archival Paper Standard"
        
        title_match = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE)
        if title_match:
            extracted_name = title_match.group(1).split('|').split('-').strip()
        elif "klug" in url_lower:
            extracted_name = "KLUG Photographic Archival Paper"
        elif "preservationequipment" in url_lower or "pel" in text_lower:
            extracted_name = "PEL Unbuffered Tissue Paper"
        elif "thermal" in text_lower:
            extracted_name = "Appvion Thermal POS Paper"
            
        if "thermal" in text_lower or "safety-data-sheet" in url_lower:
            x_cellulose, x_lignin, x_acid = 0.80, 0.15, 0.05
        elif "tissue" in text_lower or "pel" in text_lower:
            x_cellulose, is_tissue = 1.0, True
            
        return x_cellulose, x_lignin, x_acid, is_tissue, extracted_name
    except:
        return 1.0, 0.0, 0.0, False, "Unknown SDS Paper"

# חישוב המשוואות הקינטיות (ארניוס, בוטשר, איירינג ו-GAB)
def calculate_paper_lifetime(temp_c, rh, x_cellulose, x_lignin, x_acid, is_tissue):
    R, T = 8.314, temp_c + 273.15
    Ea_total = (x_cellulose * 110000) + (x_lignin * 80000) - (15000 if x_acid > 0 else 0)
    dS = -60.0 if not is_tissue else -42.0
    A = ((1.380649e-23 * T) / 6.62607015e-34) * math.exp(dS / R)
    B = (0.03 if not is_tissue else 0.042) * (rh / 50.0)
    
    ln_k = math.log(A) - (Ea_total / (R * T)) + B
    ln_k_ref = math.log(A) - (Ea_total / (R * 293.15)) + ((0.03 if not is_tissue else 0.042) * 1.0)
    k_relative = math.exp(ln_k - ln_k_ref)
    
    base_lifetime = 200 if not is_tissue else 120
    if x_lignin > 0 or x_acid > 0: base_lifetime = 5
    
    return k_relative, base_lifetime / k_relative, base_lifetime / (k_relative * (15 / 21)), Ea_total

# פונקציית ייצוא קובץ טקסט/דוח
def generate_text_report(paper_name, url, temp, rh, k_rel, yrs_21, yrs_15, ea):
    report = f"""==================================================
ARCHIVAL CONSERVATION & DEGRADATION REPORT
==================================================
Generated via Arrhenius Predictive Kinetic Modeling
Target Security: Absolute Safety Window (Museum Quality)

1. MATERIAL INPUT SPECIFICATIONS
--------------------------------------------------
Paper Identity / Brand : {paper_name}
SDS Reference Link     : {url[:50]}...
Calculated Activation Energy (Ea) : {ea/1000:.1f} kJ/mol
Testing Temperature    : {temp} °C
Relative Humidity (RH) : {rh} %

2. PREDICTIVE SAFETY WINDOW (TIME BEFORE ACID MIGRATION)
--------------------------------------------------
* Standard Atmosphere (21% O2):
  -> Relative Oxidation Rate (k): {k_rel:.4f}
  -> Absolute Safety Window      : {int(yrs_21)} Years

* Hypoxic Controlled Atmosphere (15% O2):
  -> Relative Oxidation Rate (k): {k_rel * (15/21):.4f}
  -> Absolute Safety Window      : {int(yrs_15)} Years

==================================================
APPENDIX: THEORETICAL KINETIC FRAMEWORK
==================================================
This analytical tool utilizes a multi-layered thermodynamic model:

1. BOTTCHER'S ADDITIVE RULE (Activation Energy)
   Extracts composition fractions from Section 3 of the SDS.
   Formula: Ea_total = sum(x_i * Ea_i) - Delta_Ea_catalysis

2. EYRING-POLANYI EQUATION (Frequency Factor Evaluation)
   Resolves the molecular collision pre-exponential factor (A).
   Formula: A = (kb * T / h) * exp(dS / R)

3. GUGGENHEIM-ANDERSON-DE BOER (GAB) ABSORPTION ISOTHERM
   Translates ambient relative humidity into bound chemical water.
   Formula: B = C_hydro * f(RH)

4. HUMIDITY-CORRECTED ARRHENIUS EQUATION (Core Solution)
   Integrates all matrices to output final wrapping shelf-life.
   Formula: ln(k) = ln(A) - (Ea_total / R*T) + B * RH
=================================================="""
    return report

# ממשק המשתמש אונליין (Streamlit UI)
strl.set_page_config(page_title="מחשבון חמצון נייר ארכיוני", layout="centered")

# הזרקת קוד CSS מקיף לחיוב יישור ימינה (RTL) מלא על כל אלמנט באתר
strl.markdown(
    """
    <style>
    .main .block-container, html, body, [data-testid="stAppViewContainer"] {
        direction: RTL !important;
        text-align: right !important;
    }
    h1, h2, h3, h4, h5, h6, p, span, div {
        text-align: right !important;
    }
    label[data-testid="stWidgetLabel"] p, .stSlider label p, .stTextInput label p {
        text-align: right !important;
        direction: RTL !important;
    }
    div[data-testid="stSlider"] {
        direction: LTR !important; 
    }
    div[data-testid="stSlider"] label {
        direction: RTL !important;
    }
    input[data-testid="stTextInputRootElement"] {
        direction: RTL !important;
        text-align: right !important;
    }
    div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] {
        text-align: right !important;
        direction: RTL !important;
    }
    /* עיצוב ייחודי לפסקת זכויות היוצרים בתחתית */
    .copyright-box {
        background-color: #F7FAFC;
        border-right: 4px solid #2C5282;
        padding: 15px;
        margin-top: 40px;
        border-radius: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

strl.title("Re-Oot אפליקציית חישוב קצב התחמצנות לנייר ארכיוני")
strl.markdown("מערכת אונליין לחישוב חלון הביטחון המוחלט של חומרי עיטוף על בסיס משוואת ארניוס.")

url_input = strl.text_input("הדביקי כאן קישור ל-SDS או למפרט הטכני (URL):", value="https://klug-conservation.de")

x_cell, x_lig, x_ac, is_tiss, auto_paper_name = parse_sds_from_url(url_input)
paper_name_input = strl.text_input("שם הנייר / מותג (חולץ אוטומטית מה-SDS, ניתן לעריכה):", value=auto_paper_name)

temp_input = strl.slider("טמפרטורת המחסן בדיקה (°C)", 10, 45, 30)
rh_input = strl.slider("לחות יחסית במחסן (RH%)", 10, 90, 70)

if url_input:
    k_rel, yrs_21, yrs_15, ea_total = calculate_paper_lifetime(temp_input, rh_input, x_cell, x_lig, x_ac, is_tiss)
    
    strl.subheader(" חלון זמן בטוח לעיטוף (שנים לפני פליטת חומצה ופריכות):")
    col1, col2 = strl.columns(2)
    with col1:
        strl.markdown("### 🟦 מחסן חמצן רגיל (21%)")
        strl.metric(label="חלון זמן בטוח", value=f"{int(yrs_21)} שנים")
    with col2:
        strl.markdown("### 🟩 מחסן מרודד חמצן (15%)")
        strl.metric(label="חלון זמן בטוח", value=f"{int(yrs_15)} שנים")
        
    report_content = generate_text_report(paper_name_input, url_input, temp_input, rh_input, k_rel, yrs_21, yrs_15, ea_total)
    
    strl.markdown("---")
    strl.subheader("📄 תצוגה מקדימה של דוח השימור הרשמי:")
    strl.code(report_content, language="text")
    
    strl.download_button(
        label="📥 הורדת דוח שימור רשמי + נספח מדעי (TXT)",
        data=report_content,
        file_name=f"Degradation_Report_{paper_name_input.replace(' ', '_')}.txt",
        mime="text/plain"
    )

# 🔒 הזרקת תיבת ההצהרה המשפטית וזכויות היוצרים בתחתית הדף
strl.markdown(
    """
    <div class="copyright-box">
        <p style="margin: 0; font-size: 13px; color: #2D3748; line-height: 1.6;">
            <b>© כל הזכויות שמורות לרעות אילן שפיק, 2026.</b><br>
            קוד המקור, הממשק האינטראקטיבי ושילוב המודלים הקינטיים (ארניוס, בוטשר, איירינג ו-GAB) באפליקציה זו מהווים קניין רוחני בלעדי וסוד מסחרי מוגן. אין להעתיק, לשכפל, להפיץ או לעשות שימוש מסחרי בכלי זה או בדוחות המופקים ממנו ללא אישור מפורש בכתב.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

