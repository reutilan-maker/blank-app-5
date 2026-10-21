
"""Re-Oot: archival paper documentation and relative ageing comparison.
Run: streamlit run streamlit_app.py
"""
import io
import ipaddress
import math
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup
from pypdf import PdfReader

st.set_page_config(page_title="Re-Oot | Paper Conservation", layout="centered")

LANG = st.radio("🌐 שפה / Language", ["עברית", "English"], horizontal=True)
HE = LANG == "עברית"
def tr(he, en):
    return he if HE else en

st.markdown("""<style>
.main .block-container {max-width: 900px;}
[data-testid="stAppViewContainer"] .block-container {padding-top: 2rem;}
</style>""", unsafe_allow_html=True)

st.title(tr("Re-Oot | הערכת נייר לשימור ארכיוני", "Re-Oot | Archival Paper Assessment"))
st.write(tr("חילוץ נתונים ממפרט טכני או SDS והשוואת השפעת תנאי האחסון על קצב התיישנות יחסי.",
            "Extract evidence from a technical sheet or SDS and compare relative ageing under storage conditions."))
st.info(tr("הכלי מסייע בבדיקה ראשונית בלבד. SDS אינו בהכרח מכיל מידע על התאמה ארכיונית, ואין להסיק מהמודל מספר שנות אחסון בטוחות.",
           "Screening tool only. An SDS may not contain archival suitability data. The model does not predict safe storage years."))

MAX_BYTES = 8 * 1024 * 1024
MAX_PAGES = 20
TIMEOUT = (5, 15)


def validate_public_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Enter a valid HTTP(S) URL")
    host = parsed.hostname.lower()
    if host in ("localhost",) or host.endswith((".local", ".internal")):
        raise ValueError("Private/local addresses are not supported")
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Could not resolve host") from exc
    for addr in addresses:
        ip = ipaddress.ip_address(addr[4][0])
        if not ip.is_global:
            raise ValueError("Private or non-public addresses are not supported")
    return url


def download_public(url):
    # Check each redirect target. DNS rebinding remains a deployment-level concern;
    # production deployments should additionally enforce outbound network controls.
    session = requests.Session()
    session.trust_env = True
    current = url
    for _ in range(5):
        validate_public_url(current)
        with session.get(current, headers={"User-Agent": "Re-Oot-Document-Reader/1.0"},
                         timeout=TIMEOUT, allow_redirects=False, stream=True) as resp:
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                if not location:
                    raise ValueError("Redirect without a location")
                current = urljoin(current, location)
                continue
            resp.raise_for_status()
            data = bytearray()
            for chunk in resp.iter_content(chunk_size=65536):
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError("Document exceeds the 8 MB limit")
            return bytes(data), resp.headers.get("Content-Type", ""), current
    raise ValueError("Too many redirects")


def read_document(data, content_type, final_url):
    is_pdf = data.startswith(b"%PDF") or ("application/pdf" in content_type.lower())
    if is_pdf:
        reader = PdfReader(io.BytesIO(data), strict=False)
        pages = []
        for page in reader.pages[:MAX_PAGES]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)[:180000], "PDF"
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    return (title + "\n" + soup.get_text(" ", strip=True))[:180000], "HTML"


def evidence_lines(text):
    # Snippets are evidence hints, NOT certified extraction of material composition.
    patterns = {
        "pH": r"(?i)(?:\bpH\b|acid[- ]free|חומציות|נטול חומצה)",
        "Lignin": r"(?i)(?:lignin|ליגנין)",
        "Buffering": r"(?i)(?:buffered|unbuffered|alkaline reserve|calcium carbonate|באפר|עתודה בסיסית)",
        "Standards": r"(?i)(?:ISO\s*9706|ISO\s*11108|ISO\s*18902|PAT\b|ISO\s*18916)",
        "Material": r"(?i)(?:cellulose|cotton|alpha[- ]cellulose|rag paper|תאית|כותנה)",
    }
    results = {}
    for key, pattern in patterns.items():
        snippets = []
        for match in re.finditer(pattern, text):
            excerpt = re.sub(r"\s+", " ", text[max(0, match.start()-75):match.end()+115]).strip()
            if excerpt not in snippets:
                snippets.append(excerpt)
            if len(snippets) == 4:
                break
        results[key] = snippets
    return results


def relative_temperature_factor(temp_c, reference_c, activation_energy_kj):
    # Arrhenius k(T)/k(Tref), valid only as a conditional sensitivity model.
    r = 8.314462618
    t, t_ref = temp_c + 273.15, reference_c + 273.15
    return math.exp((activation_energy_kj * 1000 / r) * (1 / t_ref - 1 / t))

st.subheader(tr("1. מקור המידע", "1. Document source"))
url = st.text_input(tr("קישור ישיר למפרט טכני / SDS / דף מוצר", "Direct link to technical sheet / SDS / product page"),
                    placeholder="https://example.org/product-specification.pdf")
upload = st.file_uploader(tr("או העלאת קובץ PDF", "Or upload a PDF"), type=["pdf"])

if "doc_result" not in st.session_state:
    st.session_state.doc_result = None

if st.button(tr("🔎 חילוץ נתונים", "🔎 Extract document data"), type="primary"):
    st.session_state.doc_result = None
    if not url.strip() and upload is None:
        st.warning(tr("יש להזין קישור או להעלות PDF.", "Enter a URL or upload a PDF."))
    else:
        try:
            if upload is not None:
                if upload.size > MAX_BYTES:
                    raise ValueError("PDF exceeds the 8 MB limit")
                data, mime, source = upload.getvalue(), "application/pdf", upload.name
            else:
                data, mime, source = download_public(url.strip())
            doc_text, doc_type = read_document(data, mime, source)
            if not doc_text.strip():
                raise ValueError("No selectable text found. Scanned PDFs require OCR.")
            st.session_state.doc_result = {
                "source": source, "type": doc_type, "text": doc_text,
                "evidence": evidence_lines(doc_text),
            }
            st.success(tr("המסמך נקרא. בדקי את הראיות והשלימי פרטים ידנית.",
                          "Document read. Review evidence and complete the assessment manually."))
        except Exception as exc:
            st.error(tr("לא ניתן לקרוא את המסמך: ", "Could not read document: ") + str(exc))

result = st.session_state.doc_result
if result:
    st.caption(tr("מקור: ", "Source: ") + result["source"] + " | " + result["type"])
    st.subheader(tr("2. ממצאים מהמסמך (טעונים בדיקה)", "2. Document evidence (verify manually)"))
    for key, snippets in result["evidence"].items():
        with st.expander(f"{key} — {len(snippets)} " + tr("אזכורים", "matches")):
            if snippets:
                for snippet in snippets:
                    st.write("• " + snippet)
            else:
                st.write(tr("לא נמצא אזכור בטקסט שנקרא.", "No mention found in extracted text."))
    with st.expander(tr("הצגת טקסט שחולץ", "Show extracted text")):
        st.text_area("Text", result["text"][:15000], height=220, disabled=True)

st.subheader(tr("3. אימות התאמה ארכיונית", "3. Archival suitability review"))
paper_name = st.text_input(tr("שם מוצר / נייר", "Paper / product name"))
standard = st.selectbox(tr("ראיה לתקן (לפי מסמך יצרן)", "Documented standard"),
    [tr("לא אומת", "Not verified"), "ISO 9706", "ISO 11108", "ISO 18902 / ISO 18916 (photographic)", tr("אחר — לבדיקה", "Other — review")])
ph = st.text_input(tr("pH מדווח (אם קיים)", "Reported pH (if available)"))
lignin = st.selectbox(tr("מידע על ליגנין", "Lignin information"),
    [tr("לא ידוע", "Unknown"), tr("נמסר כי נטול ליגנין", "Manufacturer states lignin-free"),
     tr("מכיל ליגנין", "Contains lignin")])
buffer = st.selectbox(tr("עתודה בסיסית / buffering", "Alkaline reserve / buffering"),
    [tr("לא ידוע", "Unknown"), tr("עם עתודה בסיסית", "Buffered"), tr("ללא עתודה בסיסית", "Unbuffered")])
notes = st.text_area(tr("הערות מקצועיות / ציטוט מדויק מהיצרן", "Professional notes / exact manufacturer quotation"))
st.warning(tr("הימצאות שם תקן או מונח בדף אינה מוכיחה עמידה בתקן. התאמה לחפץ מסוים דורשת בדיקה מקצועית, ובתצלומים יש לבחון גם PAT לפי הצורך.",
              "Mention of a standard does not prove compliance. Suitability is object-specific; photographic materials may require PAT evidence."))

st.subheader(tr("4. השוואת קצב התיישנות יחסי", "4. Relative ageing comparison"))
st.caption(tr("חישוב רגישות לטמפרטורה בלבד לפי ארניוס; אנרגיית השפעול היא הנחה מתכווננת, ולא נתון שנמדד עבור המוצר.",
              "Temperature-only Arrhenius sensitivity. Activation energy is an adjustable assumption, not a product-specific measured value."))
reference_temp = st.number_input(tr("טמפרטורת ייחוס (°C)", "Reference temperature (°C)"), value=20.0, min_value=0.0, max_value=50.0, step=1.0)
temp = st.slider(tr("טמפרטורת אחסון (°C)", "Storage temperature (°C)"), 0, 45, 20)
rh = st.slider(tr("לחות יחסית באחסון (%) — לתיעוד", "Storage relative humidity (%) — recorded only"), 10, 90, 50)
ea = st.slider(tr("אנרגיית שפעול משוערת (kJ/mol)", "Assumed activation energy (kJ/mol)"), 50, 150, 100, step=5)
oxygen = st.selectbox(tr("ריכוז חמצן — לתיעוד בלבד", "Oxygen concentration — recorded only"), ["21%", "15%"])
factor = relative_temperature_factor(temp, reference_temp, ea)
col1, col2 = st.columns(2)
with col1:
    st.metric(tr("קצב יחסי לעומת הייחוס", "Rate relative to reference"), f"{factor:.2f}×")
with col2:
    st.metric(tr("שינוי בקצב", "Rate change"), f"{(factor-1)*100:+.1f}%")
st.caption(tr("המודל אינו מחשב השפעת לחות או חמצן, מעבר חומצה, פריכות או תוחלת חיים בשנים. ערכי RH וחמצן נרשמים בדוח בלבד.",
              "The model does not quantify humidity, oxygen, acid migration, brittleness or lifetime in years. RH and oxygen are recorded only."))

source = result["source"] if result else tr("לא סופק מסמך שנקרא בהצלחה", "No successfully read document")
evidence = result["evidence"] if result else {}
lines = [
    "RE-OOT | ARCHIVAL PAPER SCREENING REPORT",
    "Generated (UTC): " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    "Document source: " + source,
    "Product: " + (paper_name or "Not specified"),
    "Documented standard (manual entry; not independently verified): " + standard,
    "Reported pH: " + (ph or "Not provided"),
    "Lignin: " + lignin,
    "Buffering: " + buffer,
    "Professional notes: " + (notes or "None"),
    "", "DOCUMENT TEXT MATCHES (not proof of compliance):",
]
for key, snippets in evidence.items():
    lines.append(key + ":")
    lines.extend(" - " + s for s in snippets) if snippets else lines.append(" - No match")
lines += [
    "", "CONDITIONAL TEMPERATURE SENSITIVITY (ARRHENIUS):",
    f"Reference temperature: {reference_temp:.1f} C",
    f"Storage temperature: {temp} C",
    f"Assumed activation energy: {ea} kJ/mol",
    f"Relative rate k(T)/k(Tref): {factor:.4f}",
    f"Recorded RH (not included in calculation): {rh}%",
    f"Recorded O2 (not included in calculation): {oxygen}",
    "", "LIMITATIONS:",
    "This is not a certificate of archival compliance.",
    "No absolute safe years, acid migration date, or brittleness threshold is predicted.",
    "Material-specific kinetic parameters and validated ageing data are required for such predictions.",
    "SDS and generic product pages may omit necessary archival testing data.",
]
report = "\n".join(lines)
st.subheader(tr("5. דוח להורדה", "5. Download report"))
with st.expander(tr("תצוגה מקדימה", "Report preview")):
    st.code(report, language="text")
st.download_button(tr("📄 הורדת דוח TXT", "📄 Download TXT report"), report,
                   file_name="ReOot_Conservation_Report.txt", mime="text/plain")
st.divider()
st.caption(tr("Re-Oot — כלי תומך החלטה לשימור; נדרש אימות מול מסמכי יצרן ותקנים רלוונטיים.",
              "Re-Oot — conservation decision support; verify against manufacturer documentation and relevant standards."))
