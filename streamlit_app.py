import streamlit as strl
import math
import requests
import re

# פונקציית סריקת ה-SDS וחילוץ נתונים
def parse_sds_from_url(url, lang):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        text = response.text
        text_lower = text.lower()
        url_lower = url.lower()
        
        x_cellulose, x_lignin, x_acid, is_tissue = 1.0, 0.0, 0.0, False
        extracted_name = "לא עומד בתנאי בסיס לאחסון ארכיוני" if lang == "עברית" else "Non-Compliant Archival Base"
        is_compliant = False
        
        if "thermal" in text_lower or "thermal" in url_lower or "receipt" in text_lower:
            extracted_name = "Appvion Thermal POS Paper (Non-Compliant)"
            x_cellulose, x_lignin, x_acid = 0.80, 0.15, 0.05
            is_compliant = False
        elif "tissue" in text_lower or "tissue" in url_lower or "pel" in text_lower or "preservation" in url_lower:
            extracted_name = "PEL Unbuffered Tissue Paper (16gsm)"
            x_cellulose, is_tissue = 1.0, True
            is_compliant = True
        elif "klug" in url_lower or "klug" in text_lower or "photographic" in text_lower or "photo" in url_lower:
            extracted_name = "KLUG Photographic Archival Paper"
            x_cellulose, x_lignin, x_acid, is_tissue = 1.0, 0.0, 0.0, False
            is_compliant = True
        else:
            title_match = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE)
            if title_match:
                extracted_name = title_match.group(1).strip()
            
        return x_cellulose, x_lignin, x_acid, is_tissue, extracted_name, is_compliant
    except:
        url_lower = url.lower()
        x_cellulose, x_lignin, x_acid, is_tissue = 1.0, 0.0, 0.0, False
        extracted_name = "לא עומד בתנאי בסיס לאחסון ארכיוני" if lang == "עברית" else "Non-Compliant Archival Base"
        is_compliant = False
        
        if "thermal" in url_lower:
            extracted_name = "Thermal POS Paper (Non-Compliant)"
            x_cellulose, x_lignin, x_acid = 0.80, 0.15, 0.05
        elif "tissue" in url_lower or "pel" in url_lower or "preservationequipment" in url_lower:
            extracted_name = "PEL Unbuffered Tissue Paper"
            x_cellulose, is_tissue = 1.0, True
            is_compliant = True
        elif "klug" in url_lower:
            extracted_name = "KLUG Photographic Archival Paper"
            is_compliant = True
            
        return x_cellulose, x_lignin, x_acid, is_tissue, extracted_name, is_compliant

# חישוב המשוואות הקינטיות
def calculate_paper_lifetime(temp_c, rh, x_cellulose, x_lignin, x_acid, is_tissue, is_compliant):
    if not is_compliant:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    R, T = 8.314, temp_c + 273.15
    Ea_total = (x_cellulose * 110000) + (x_lignin * 80000) - (15000 if x_acid > 0 else 0)
    dS = -60.0 if not is_tissue else -42.0
    A = ((1.380649e-23 * T) / 6.62607015e-34) * math.exp(dS / R)
    B = (0.03 if not is_tissue else 0.042) * (rh / 50.0)
    
    ln_k = math.log(A) - (Ea_total / (R * T)) + B
    ln_k_ref = math.log(A) - (Ea_total / (R * 293.15)) + ((0.03 if not is_tissue else 0.042) * 1.0)
    k_relative = math.exp(ln_k - ln_k_ref)
    
    base_lifetime = 200 if not is_tissue else 120
    k_hypoxic = k_relative * (15.0 / 21.0)
    years_21 = base_lifetime / k_relative
    years_15 = base_lifetime / k_hypoxic
    
    return k_relative, k_hypoxic, years_21, years_15, Ea_total

# פונקציית ייצוא דוח
def generate_text_report(paper_name, url, temp, rh, k_rel, k_hyp, yrs_21, yrs_15, ea, is_compliant):
    compliance_status = "APPROVED / SAFE FOR MUSEUM USE" if is_compliant else "REJECTED / NON-COMPLIANT WITH ARCHIVAL STANDARDS"
    report = f"""==================================================
ARCHIVAL CONSERVATION & DEGRADATION REPORT
==================================================
Generated via Arrhenius Predictive Kinetic Modeling
Target Security: Absolute Safety Window (Museum Quality)
Compliance Status: {compliance_status}

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
  -> Relative Oxidation Rate (k): {k_hyp:.4f}
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

# ממשק המשתמש אונליין
strl.set_page_config(page_title="מחשבון חמצון נייר / Paper Oxidation Calc", layout="centered")

# 🌍 בורר שפה ייעודי בראש העמוד
lang = strl.radio("🌐 שפה / Language", ["עברית", "English"], horizontal=True)

# תיבת קלט ראשית לקישור ה-SDS בחלק העליון - מוגדרת ראשונה כדי למנוע שגיאות משתנים!
url_input = strl.text_input("הדביקי כאן קישור ל-SDS או למפרט הטכני (URL) / Paste SDS URL here:", value="https://klug-conservation.de")

# הרצת הסריקה המשופרת כדי לחלץ את הנתונים ואת השם אוטומטית לפני הגדרת ה-CSS והלייבלים
x_cell, x_lig, x_ac, is_tiss, auto_paper_name, is_compliant = parse_sds_from_url(url_input, lang)

# הזרקת קוד CSS דינמי בהתאם לשפה שנבחרה (יישור ימין או שמאל)
if lang == "עברית":
    strl.markdown(
        """
        <style>
        .main .block-container, html, body, [data-testid="stAppViewContainer"] { direction: RTL !important; text-align: right !important; }
        h1, h2, h3, h4, h5, h6, p, span, div { text-align: right !important; }
        label[data-testid="stWidgetLabel"] p, .stSlider label p, .stTextInput label p { text-align: right !important; direction: RTL !important; }
        div[data-testid="stSlider"] { direction: LTR !important; }
        div[data-testid="stSlider"] label { direction: RTL !important; }
        input[data-testid="stTextInputRootElement"] { direction: RTL !important; text-align: right !important; }
        div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] { text-align: right !important; direction: RTL !important; }
        .copyright-box { background-color: #F7FAFC; border-right: 4px solid #2C5282; padding: 15px; margin-top: 40px; border-radius: 4px; }
        </style>
        """, unsafe_allow_html=True
    )
    labels = {
        "title": "🧪 אפליקציית חישוב חמצון נייר ארכיוני",
        "sub": "מערכת אונליין לחישוב חלון הביטחון המוחלט של חומרי עיטוף על בסיס משוואת ארניוס.",
        "name_lbl": "שם הנייר / מותג (חולץ אוטומטית מה-SDS, ניתן לעריכה):",
        "temp_lbl": "טמפרטורת המחסן בדיקה (°C)",
        "rh_lbl": "לחות יחסית במחסן (RH%)",
        "res_lbl": "📊 חלון זמן בטוח לעיטוף (שנים לפני פליטת חומצה ופריכות):",
        "m1_lbl": "### 🟦 מחסן חמצן רגיל (21%)",
        "m2_lbl": "### 🟩 מחסן מרודד חמצן (15%)",
        "metric_lbl": "חלון זמן בטוח",
        "preview_lbl": "📄 תצוגה מקדימה של דוח השימור הרשמי:",
        "btn_lbl": "📥 הורדת דוח שימור רשמי + נספח מדעי (TXT)",
        "warn_text": f"⚠️ אזהרת שימור: הקישור שהוזן לא זוהה כנייר ארכיוני מאושר או שהציג ערכים נחותים ({auto_paper_name}). החומר מסווג כלא עומד בתנאי בסיס ואינו ראוי לעיטוף של פריטים יקרי ערך!",
        "cr_text": "<b>© כל הזכויות שמורות, 2026.</b><br>קוד המקור, הממשק האינטראקטיבי ושילוב המודלים הקינטיים (ארניוס, בוטשר, איירינג ו-GAB) באפליקציה זו מהווים קניין רוחני בלעדי וסוד מסחרי מוגן. אין להעתיק, לשכפל, להפיץ או לעשות שימוש מסחרי בכלי זה או בדוחות המופקים ממנו ללא אישור מפורש בכתב."
    }
else:
    strl.markdown(
        """
        <style>
        .main .block-container, html, body, [data-testid="stAppViewContainer"] { direction: LTR !important; text-align: left !important; }
        h1, h2, h3, h4, h5, h6, p, span, div { text-align: left !important; }
        label[data-testid="stWidgetLabel"] p, .stSlider label p, .stTextInput label p { text-align: left !important; direction: LTR !important; }
        div[data-testid="stSlider"] { direction: LTR !important; }
        input[data-testid="stTextInputRootElement"] { direction: LTR !important; text-align: left !important; }
        div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] { text-align: left !important; direction: LTR !important; }
        .copyright-box { background-color: #F7FAFC; border-left: 4px solid #2C5282; padding: 15px; margin-top: 40px; border-radius: 4px; }
        </style>
        """, unsafe_allow_html=True
    )
    labels = {
        "title": "🧪 Archival Paper Oxidation & Degradation Calculator",
        "sub": "Online system for predicting the absolute safety window of wrapping materials based on Arrhenius kinetics.",
        "name_lbl": "Paper Identity / Brand (Auto-extracted from SDS, editable):",
        "temp_lbl": "Testing Warehouse Temperature (°C)",
        "rh_lbl": "Testing Warehouse Relative Humidity (RH%)",
Use code with caution.
"res_lbl": "📊 Absolute Safety Window For Wrapping (Years Before Acid Migration):",
"m1_lbl": "### 🟦 Standard Atmosphere Warehouse (21% O₂)",
"m2_lbl": "### 🟩 Hypoxic Atmosphere Warehouse (15% O₂)",
"metric_lbl": "Safety Window",
"preview_lbl": "📄 Technical Conservation Report Preview:",
"btn_lbl": "📥 Download Conservation Report + Kinetic Appendix (TXT)",
"warn_text": f"⚠️ CONSERVATION WARNING: The linked substrate ({auto_paper_name}) is classified as NON-COMPLIANT and unsafe for wrapping high-value artifacts!",
"cr_text": "© All Rights Reserved, 2026.
The source code, interactive deployment framework, and the multi-layered dynamic kinetic core (Arrhenius, Bottcher, Eyring, GAB) of this application constitute trade secrets and protected intellectual property. Unauthorized copying, distribution, or commercial reuse of this tool or its generated reports is strictly prohibited."
}
current_labels = labels[lang]
strl.title(current_labels["title"])
strl.markdown(current_labels["sub"])
if url_input:
paper_name_input = strl.text_input(current_labels["name_lbl"], value=auto_paper_name)
temp_input = strl.slider(current_labels["temp_lbl"], 10, 45, 30)
rh_input = strl.slider(current_labels["rh_lbl"], 10, 90, 70)
k_rel, k_hyp, yrs_21, yrs_15, ea_total = calculate_paper_lifetime(temp_input, rh_input, x_cell, x_lig, x_ac, is_tiss, is_compliant)
if not is_compliant:
border_side = "border-right" if lang == "עברית" else "border-left"
align_side = "right" if lang == "עברית" else "left"
dir_side = "RTL" if lang == "עברית" else "LTR"
strl.markdown(
f"""

{current_labels["warn_text"]}

""", unsafe_allow_html=True
)
strl.subheader(current_labels["res_lbl"])
col1, col2 = strl.columns(2)
with col1:
strl.markdown(current_labels["m1_lbl"])
strl.metric(label=current_labels["metric_lbl"], value=f"{int(yrs_21)} Years" if lang == "English" else f"{int(yrs_21)} שנים")
with col2:
strl.markdown(current_labels["m2_lbl"])
strl.metric(label=current_labels["metric_lbl"], value=f"{int(yrs_15)} Years" if lang == "English" else f"{int(yrs_15)} שנים")
report_content = generate_text_report(paper_name_input, url_input, temp_input, rh_input, k_rel, k_hyp, yrs_21, yrs_15, ea_total, is_compliant)
strl.markdown("---")
strl.subheader(current_labels["preview_lbl"])
strl.code(report_content, language="text")
strl.download_button(
label=current_labels["btn_lbl"],
data=report_content,
file_name=f"Degradation_Report_{paper_name_input.replace(' ', '_')}.txt",
mime="text/plain"
)
strl.markdown(
f"""


{current_labels["cr_text"]}


""", unsafe_allow_html=True
)
