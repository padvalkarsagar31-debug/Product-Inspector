import os
import json
import ssl
import urllib.request
import time
import base64
import streamlit as st

CANDIDATE_MODELS = ["gemini-flash-latest", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

SAMPLE_PRODUCTS = [
    {"name": "Amul Butter (UPC: 8901262010025)", "upc": "8901262010025"},
    {"name": "Maggi 2-Minute Noodles Masala (UPC: 8901058853609)", "upc": "8901058853609"},
    {"name": "Parle-G Glucose Biscuits (UPC: 8901719101103)", "upc": "8901719101103"},
    {"name": "Cadbury Dairy Milk Silk (UPC: 8901233025505)", "upc": "8901233025505"},
    {"name": "Tata Salt (UPC: 8901058885105)", "upc": "8901058885105"}
]

SYSTEM_PROMPT = """You are an expert food scientist, consumer goods manufacturing analyst, and clinical nutritionist specializing in the Indian packaged food market (FSSAI guidelines, local ingredients, and dietary patterns).
Analyze the given product (either from its UPC barcode, Indian product name, or product package image).

You MUST respond strictly with a valid JSON object following this exact schema:
{
  "barcode": "string or UPC code if provided",
  "productName": "string",
  "brand": "string",
  "category": "string (e.g., Dairy, Snacks, Beverage, Bakery, Cereal, Condiment)",
  "summary": "Concise 2-sentence executive summary of the product and its nutritional standing in the Indian context",
  "confidenceScore": 95,
  "manufacturing": {
    "summary": "How this product is made industrially or traditionally",
    "steps": [
      {
        "stepName": "Step title",
        "description": "Specific processing description (e.g. wet milling, high-pressure extrusion, pasteurization, emulsification)",
        "type": "raw | extraction | thermal | chemical | mixing | packaging",
        "isIndustrial": true
      }
    ],
    "syntheticProcesses": ["List of synthetic or ultra-processing techniques used, e.g. chemical bleaching, solvent extraction, artificial flavoring"],
    "processingLevel": "Minimal | Culinary Processed | Moderately Processed | Ultra-Processed"
  },
  "healthRating": {
    "overallScore": 65,
    "grade": "A | B | C | D | E",
    "nutriScore": {
      "grade": "A | B | C | D | E",
      "points": 12,
      "rationale": "Explanation based on official calculation (penalties for calories/sugars/sat-fat/sodium vs points for fiber/protein)",
      "negativePoints": [{"label": "Sugars", "value": "22g/100g", "impact": "High penalty"}],
      "positivePoints": [{"label": "Fiber", "value": "4g/100g", "impact": "Moderate benefit"}]
    },
    "novaGroup": {
      "group": 4,
      "title": "Group 4 - Ultra-Processed Food (UPF)",
      "rationale": "Clear scientific rationale according to NOVA classification system (Monteiro et al.)"
    },
    "cleanLabelScore": 58,
    "harmfulAdditivesCount": 2
  },
  "potential": {
    "healthBenefits": [
      {"title": "Benefit title", "description": "Mechanistic health benefit", "tag": "Cardio / Muscle / Gut / Energy"}
    ],
    "healthRisks": [
      {"title": "Risk / Concern", "description": "Mechanistic health risk or long-term consequence", "severity": "low | moderate | high"}
    ],
    "dietarySuits": [
      {"diet": "Vegan", "suitable": true, "note": "Contains no animal products"},
      {"diet": "Jain Dietary Compliant", "suitable": false, "note": "Contains root vegetables or restricted ingredients"},
      {"diet": "Gluten-Free", "suitable": true, "note": "No wheat, barley, or rye ingredients"}
    ],
    "healthierAlternatives": [
      {"name": "Cleaner brand or wholesome alternative available in India", "brand": "Brand", "whyBetter": "Less added sugar and zero emulsifiers", "estimatedPrice": "₹60"}
    ]
  },
  "price": {
    "estimatedPriceRangeINR": "₹40 - ₹60",
    "typicalServingCost": "₹10.00 / serving",
    "valueVerdict": "Great Value | Fair Price | Overpriced for Quality | Premium Tier",
    "pricingAnalysis": "Economic assessment of raw ingredient cost vs Indian retail shelf markup"
  },
  "details": {
    "ingredients": [
      {"name": "Ingredient name", "purpose": "Function (e.g. Bulk, Emulsifier, Sweetener, Leavening)", "riskLevel": "safe | caution | hazardous", "notes": "Details on origin or health impact"}
    ],
    "additives": [
      {"codeOrName": "Additive code or name", "function": "Preservative / Color / Flavor enhancer", "safetyAssessment": "FSSAI / EFSA status and metabolic impact", "risk": "low | moderate | high"}
    ],
    "nutritionPerServing": {
      "servingSize": "e.g., 30g",
      "calories": "150 kcal",
      "totalFat": "8g",
      "saturatedFat": "1g",
      "sodium": "210mg",
      "totalCarbs": "18g",
      "dietaryFiber": "1g",
      "sugars": "1g",
      "protein": "2g"
    },
    "sustainability": {
      "packagingMaterial": "Plastic laminate / Glass jar / Cardboard",
      "recyclability": "Often non-recyclable curbside / Widely recyclable",
      "carbonFootprint": "Low | Moderate | High",
      "environmentalNotes": "Sourcing and agricultural impact in the region"
    },
    "certifications": ["FSSAI", "ISI Mark", "Agmark", "India Organic"]
  }
}
"""

st.set_page_config(
    page_title="Product Inspector & Health Rating - India",
    page_icon="🇮🇳",
    layout="wide"
)

def call_gemini_api(payload, api_key):
    data_bytes = json.dumps(payload).encode("utf-8")
    ctx = ssl.create_default_context()
    last_err = None

    for model in CANDIDATE_MODELS:
        url = API_URL_TEMPLATE.format(model=model, key=api_key)
        for attempt in range(1, 3):
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "aistudio-build"
                },
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                    res_body = response.read().decode("utf-8")
                    res_json = json.loads(res_body)
                    
                    candidates = res_json.get("candidates", [])
                    if not candidates:
                        raise ValueError("Gemini API returned no candidates.")
                    
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    if not parts:
                        raise ValueError("Candidate contains no content parts.")
                    
                    text_response = parts[0].get("text", "").strip()
                    
                    if text_response.startswith("```json"):
                        text_response = text_response[7:]
                    if text_response.startswith("```"):
                        text_response = text_response[3:]
                    if text_response.endswith("```"):
                        text_response = text_response[:-3]
                    text_response = text_response.strip()
                    
                    return json.loads(text_response)
            except urllib.error.HTTPError as e:
                last_err = e
                try:
                    error_msg = e.read().decode("utf-8")
                except Exception:
                    error_msg = str(e)
                if e.code in (429, 503, 500):
                    time.sleep(1.2 * attempt)
                    continue
                st.error(f"HTTP Error {e.code}: {error_msg}")
                return None
            except Exception as e:
                last_err = e
                time.sleep(1.0)
                continue

    st.error(f"Fatal Error calling Gemini API: {last_err}")
    return None

def analyze_upc(upc_or_name, api_key):
    prompt_text = f"Analyze this product available in India by barcode or exact product name: '{upc_or_name}'."
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}
    }
    return call_gemini_api(payload, api_key)

def analyze_image(image_bytes, mime_type, api_key):
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {"inlineData": {"mimeType": mime_type, "data": b64_data}},
                    {"text": "Identify this Indian grocery product from its package, barcode, or ingredients label, and provide comprehensive analysis including FSSAI context."}
                ]
            }
        ],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}
    }
    return call_gemini_api(payload, api_key)

# Sidebar Configuration
st.sidebar.title("🇮🇳 Settings (India)")
api_key_input = st.sidebar.text_input("Gemini API Key", type="password", value=os.environ.get("GEMINI_API_KEY", ""))

st.sidebar.markdown("---")
input_mode = st.sidebar.radio("Select Input Mode", ["Barcode / Indian Brand or Product Name", "Popular Indian Sample", "Product Image Upload"])

target_input = None
uploaded_image = None

if input_mode == "Barcode / Indian Brand or Product Name":
    target_input = st.sidebar.text_input("Enter Barcode or Product Name", "Amul Butter")
elif input_mode == "Popular Indian Sample":
    sample_choice = st.sidebar.selectbox("Choose Sample", SAMPLE_PRODUCTS, format_func=lambda x: x["name"])
    target_input = sample_choice["upc"]
else:
    uploaded_image = st.sidebar.file_uploader("Upload Product Image", type=["jpg", "jpeg", "png", "webp"])

analyze_btn = st.sidebar.button("Run Inspection", type="primary")

# Main Page Layout
st.title("📦 Indian Product Inspector & Health Rating")
st.markdown("Analyze FSSAI compliance, manufacturing pathways, local ingredient quality, and nutritional impact for products in India.")

if analyze_btn:
    if not api_key_input:
        st.error("Please provide your Gemini API Key in the sidebar.")
    else:
        with st.spinner("Analyzing product data for the Indian market..."):
            result = None
            if input_mode in ["Barcode / Indian Brand or Product Name", "Popular Indian Sample"] and target_input:
                result = analyze_upc(target_input, api_key_input)
            elif input_mode == "Product Image Upload" and uploaded_image:
                mime = uploaded_image.type
                result = analyze_image(uploaded_image.getvalue(), mime, api_key_input)
            else:
                st.warning("Please enter valid input or upload an image.")

            if result:
                st.session_state["result"] = result

if "result" in st.session_state:
    data = st.session_state["result"]
    
    # Overview Section
    st.markdown("### 📋 Product Identification")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Product Name", data.get("productName", "N/A"))
        st.write(f"**Brand:** {data.get('brand', 'N/A')}")
    with col2:
        st.metric("Category", data.get("category", "N/A"))
        st.write(f"**Barcode/UPC:** {data.get('barcode', 'N/A')}")
    with col3:
        st.metric("Confidence Score", f"{data.get('confidenceScore', 0)}%")
    
    st.info(data.get("summary", ""))

    # Health Ratings
    st.markdown("### 🥗 Healthiness Standards Rating")
    hr = data.get("healthRating", {})
    h1, h2, h3, h4 = st.columns(4)
    with h1:
        st.metric("Overall Score", f"{hr.get('overallScore', 0)}/100")
    with h2:
        st.metric("Nutri-Score", hr.get("nutriScore", {}).get("grade", "N/A"))
    with h3:
        st.metric("Clean Label Score", f"{hr.get('cleanLabelScore', 'N/A')}/100")
    with h4:
        st.metric("Harmful Additives", hr.get("harmfulAdditivesCount", 0))

    nova = hr.get("novaGroup", {})
    st.markdown(f"**NOVA Group:** {nova.get('title', 'N/A')}")
    st.caption(nova.get("rationale", ""))

    nutri = hr.get("nutriScore", {})
    if nutri.get("rationale"):
        st.markdown(f"**Nutri-Score Rationale:** {nutri.get('rationale')}")

    # Manufacturing Pipeline
    st.markdown("### ⚙️ Manufacturing & Processing Pipeline")
    mfg = data.get("manufacturing", {})
    st.write(f"**Processing Level:** {mfg.get('processingLevel', 'N/A')}")
    st.write(f"**Overview:** {mfg.get('summary', '')}")
    
    if mfg.get("steps"):
        st.markdown("#### Step-by-Step Flow")
        for idx, step in enumerate(mfg.get("steps", []), 1):
            tag = "🏭 Industrial" if step.get("isIndustrial") else "🌱 Natural"
            with st.expander(f"Step {idx}: {step.get('stepName')} ({tag})"):
                st.write(step.get("description"))

    # Health Impacts & Risks
    st.markdown("### ⚡ Potential Health Impact & Risks")
    pot = data.get("potential", {})
    
    col_ben, col_risk = st.columns(2)
    with col_ben:
        st.markdown("#### Positive Benefits")
        for b in pot.get("healthBenefits", []):
            st.success(f"**[{b.get('tag', 'Health')}] {b.get('title')}:** {b.get('description')}")
            
    with col_risk:
        st.markdown("#### Risks & Watchouts")
        for r in pot.get("healthRisks", []):
            st.error(f"**[{r.get('severity', 'moderate').upper()}] {r.get('title')}:** {r.get('description')}")

    # Dietary Suits & Alternatives
    suits = pot.get("dietarySuits", [])
    if suits:
        st.markdown("#### Dietary Compliance (India)")
        cols = st.columns(len(suits))
        for i, s in enumerate(suits):
            with cols[i]:
                icon = "✅" if s.get("suitable") else "❌"
                st.write(f"{icon} **{s.get('diet')}**")
                st.caption(s.get("note", ""))

    alts = pot.get("healthierAlternatives", [])
    if alts:
        st.markdown("#### ⭐ Healthier Swaps in India")
        for alt in alts:
            st.info(f"**{alt.get('name')}** ({alt.get('brand')}): {alt.get('whyBetter')} (~{alt.get('estimatedPrice', 'N/A')})")

    # Price & Economics (INR)
    st.markdown("### 💰 Price & Economic Value (₹ INR)")
    price = data.get("price", {})
    p1, p2, p3 = st.columns(3)
    with p1:
        st.metric("Estimated Price Range", price.get("estimatedPriceRangeINR", price.get("estimatedPriceRangeUSD", "N/A")))
    with p2:
        st.metric("Cost Per Serving", price.get("typicalServingCost", "N/A"))
    with p3:
        st.metric("Value Verdict", price.get("valueVerdict", "N/A"))
    st.write(price.get("pricingAnalysis", ""))

    # Nutrition & Additives
    st.markdown("### 📊 Nutrition & Additives Analysis")
    det = data.get("details", {})
    nutr = det.get("nutritionPerServing", {})
    if nutr:
        st.markdown(f"**Nutrition (Per {nutr.get('servingSize', 'serving')}):**")
        n_col1, n_col2, n_col3, n_col4 = st.columns(4)
        n_col1.metric("Calories", nutr.get("calories", "N/A"))
        n_col2.metric("Total Fat", nutr.get("totalFat", "N/A"))
        n_col3.metric("Sodium", nutr.get("sodium", "N/A"))
        n_col4.metric("Protein", nutr.get("protein", "N/A"))

    additives = det.get("additives", [])
    if additives:
        st.markdown("#### Flagged Additives")
        for add in additives:
            st.warning(f"**{add.get('codeOrName')}** ({add.get('function')}): Risk - {add.get('risk', '').upper()} | {add.get('safetyAssessment')}")

    # Certifications (FSSAI, etc.)
    certs = det.get("certifications", [])
    if certs:
        st.markdown(f"**Certifications & Regulatory Compliance:** {', '.join(certs)}")

    # Raw JSON toggle
    with st.expander("View Raw JSON Output"):
        st.json(data)