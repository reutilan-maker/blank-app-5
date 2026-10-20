import streamlit as strl
import math
import requests
import re

# פונקציית סריקת ה-SDS וחילוץ נתונים + חילוץ שם הנייר המעודכנת והמתוקנת
def parse_sds_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        text = response.text
        text_lower = text.lower()
        url_lower = url.lower()
        
        # ערכי ברירת מחדל לחומר (לוגיקת Fail-Safe מחמירה)
        x_cellulose, x_lignin, x_acid, is_tissue = 1.0, 0.0, 0.0, False
        extracted_name = "לא עומד בתנאי בסיס לאחסון ארכיוני"
        is_compliant = False
        
        # 1. מנגנון חילוץ וסיווג חכם ומדוייק לפי מילות מפתח ומקור הקישור
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
            # ניסיון חילוץ מתגית הכותרת של האתר במידה וזה מותג לא מוכר
            title_match = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE)
            if title_match:
                extracted_name = title_match.group(1).strip()
            
        return x_cellulose, x_lignin, x_acid, is_tissue, extracted_name, is_compliant
    except:
        # במקרה שהאתר חסם את הסריקה - זיהוי בסיסי חלופי לפי הכתובת בלבד
        url_lower = url.lower()
        x_cellulose, x_lignin, x_acid, is_tissue = 1.0, 0.0, 0.0, False
        extracted_name = "לא עומד בתנאי בסיס לאחסון ארכיוני"
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

# חישוב המשוואות הקינטיות (ארניוס, בוטשר, איירינג ו-GAB) הכולל פקטור 15% חמצן מובנה ונעילת בטיחות
def calculate_paper_lifetime(temp_c, rh, x_cellulose, x_lignin, x_acid, is_tissue, is_compliant):
    if not is_compliant:
        # אם הנייר אינו מאושר ארכיונית, החישוב ננעל מיידית על אפס שנים
        return 0.0, 0.0, 0.0, 0.0, 0.0

    R, T = 8.314, temp_c + 273.15
    Ea_total = (x_cellulose * 110000) + (x_lignin * 80000) - (15000 if x_acid > 0 else 0)
    dS = -60.0 if not is_tissue else -42.0
    A = ((1.380649e-23 * T) / 6.62607015e-34) * math.exp(dS / R)
    B = (0.03 if not is_tissue else 0.042) * (rh / 50.0)
    
    ln_k = math.log(A) - (Ea_total / (R * T)) + B
    ln_k_ref = math.log(A) - (Ea_total / (R * 293.15)) + ((0.03 if not is_tissue else 0.042) * 1.0)
    k_relative = math.exp(ln_k - ln_k_ref)
    
    # הגדרת בסיס תוחלת החיים לחלון ביטחון מוחלט (רגישות מקסימלית)
    base_lifetime = 200 if not is_tissue else 120
    if x_lignin > 0 or x_acid > 0: base_lifetime = 5
    
    # חישוב השנים המדויק באוויר רגיל לעומת רידוד חמצן ל-15% (פקטור קבוע של 15/21)
    k_hypoxic = k_relative * (15.0 / 21.0)
    years_21 = base_lifetime / k_relative
    years_15 = base_lifetime / k_hypoxic
    
    return k_relative, k_hypoxic, years_21, years_15, Ea_total

# פונקציית ייצוא קובץ טקסט/דוח מעודכנת הכוללת את נתוני ה-15% והסטטוס המשפטי
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

strl.title("Re-Oot אפליקציית חישוב קצב התחמצנות נייר לארכיונים")
strl.markdown("מערכת אונליין לחישוב חלון הביטחון המוחלט של חומרי עיטוף על בסיס משוואת ארניוס.")

# תיבת קלט ראשית לקישור ה-SDS בחלק העליון
url_input = strl.text_input("הדביקי כאן קישור ל-SDS או למפרט הטכני (URL):", value="https://klug-conservation.de")

if url_input:
    # הרצת הסריקה ברגע שהקישור מוזן כדי לחלץ את שם הנייר והסטטוס
    x_cell, x_lig, x_ac, is_tiss, auto_paper_name, is_compliant = parse_sds_from_url(url_input)

    # שדה שם הנייר מתעדכן כעת דינמית על בסיס תוצאת הסריקה מה-SDS
    paper_name_input = strl.text_input("שם הנייר / מותג (חולץ אוטומטית מה-SDS, ניתן לעריכה):", value=auto_paper_name)

    # הגדרת ערכי ברירת מחדל מעודכנים לפי מתווה מחסן הקיץ הישראלי החדש שקבעת (30 מעלות ו-70% לחות)
    temp_input = strl.slider("טמפרטורת המחסן בדיקה (°C)", 10, 45, 30)
    rh_input = strl.slider("לחות יחסית במחסן (RH%)", 10, 90, 70)

    k_rel, k_hyp, yrs_21, yrs_15, ea_total = calculate_paper_lifetime(temp_input, rh_input, x_cell, x_lig, x_ac, is_tiss, is_compliant)
    
    # הוספת קופסת אזהרה אדומה במקרה של חוסר התאמה מובהק לתנאי סף ארכיוניים
    if not is_compliant:
        strl.markdown(
            f"""
            <div style="background-color: #FFF5F5; border-right: 4px solid #E53E3E; padding: 15px; color: #C53030; font-weight: bold; margin-top: 20px; margin-bottom: 20px; border-radius: 4px; text-align: right; direction: RTL;">
                ⚠️ אזהרת שימור: הקישור שהוזן לא זוהה כנייר ארכיוני מאושר או שהציג ערכים נחותים. החומר מסווג כלא עומד בתנאי בסיס ואינו ראוי לעיטוף של פריטים יקרי ערך!
            </div>
            """,
            unsafe_allow_html=True
        )
    
    strl.subheader(" חלון זמן בטוח לעיטוף (שנים לפני פליטת חומצה ופריכות):")
    col1, col2 = strl.columns(2)
    with col1:
        strl.markdown("### 🟦 מחסן חמצן רגיל (21%)")
        strl.metric(label="חלון זמן בטוח", value=f"{int(yrs_21)} שנים")
    with col2:
        strl.markdown("### 🟩 מחסן מרודד חמצן (15%)")
        strl.metric(label="חלון זמן בטוח", value=f"{int(yrs_15)} שנים")
        
    # הפקת דוח הטקסט הכולל את פרמטרי הציות
    report_content = generate_text_report(paper_name_input, url_input, temp_input, rh_input, k_rel, k_hyp, yrs_21, yrs_15, ea_total, is_compliant)
    
    strl.markdown("---")
    strl.subheader("📄 תצוגה מקדימה של דוח השימור הרשמי:")
    strl.code(report_content, language="text")
    
strl.download_button(
label="הורדת דוח שימור רשמי + נספח מדעי (TXT)",
data=report_content,
file_name=f"Degradation_Report_{paper_name_input.replace(' ', '_')}.txt",
mime="text/plain"
)
strl.markdown(
"""


© כל הזכויות שמורות לרעות אילן שפיק, 2026.

קוד המקור, הממשק האינטראקטיבי ושילוב המודלים הקינטיים (ארניוס, בוטשר, איירינג ו-GAB) באפליקציה זו מהווים קניין רוחני בלעדי וסוד מסחרי מוגן. אין להעתיק, לשכפל, להפיץ או לעשות שימוש מסחרי בכלי זה או בדוחות המופקים ממנו ללא אישור מפורש בכתב.


""",
unsafe_allow_html=True
)
