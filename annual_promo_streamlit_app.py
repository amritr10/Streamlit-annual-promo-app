#!/usr/bin/env python
import streamlit as st
import pandas as pd
import re
from streamlit_gsheets import GSheetsConnection

# ------------------------- Page Setup -------------------------
st.set_page_config(page_title="Annual Promotion", layout="wide")

# ------------------------- Custom CSS -------------------------
st.markdown("""
    <style>
    /* Promotion Header Style */
    .promo-header {
        text-align: center;
        padding: 20px;
        background-color: #f2f2f2;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .promo-header h1 {
        color: #d6336c;
        font-size: 3em;
        margin: 0;
    }
    /* Category Section Header */
    .section-header {
        padding: 10px;
        background-color: #e9ecef;
        border-radius: 5px;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    .section-header h2 {
        margin: 0;
        color: #343a40;
    }
    /* Series Subsection Header */
    .subsection-header {
        padding: 5px 10px;
        background-color: #f8f9fa;
        border-left: 4px solid #d6336c;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    .subsection-header h3 {
        margin: 0;
        color: #495057;
        margin-left: 10px;
    }
    /* Buy Button Style */
    .buy-button {
        background-color: #d6336c;
        color: white;
        border: none;
        padding: 10px 20px;
        font-size: 16px;
        border-radius: 5px;
        cursor: pointer;
    }
    .buy-button:hover {
        background-color: #bd2130;
    }
    /* Style for HTML details element */
    details {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 10px;
        margin-bottom: 10px;
    }
    details summary {
        outline: none;
        cursor: pointer;
    }
    /* Series image style */
    .series-image {
        width: 200px;
        height: auto;
        vertical-align: middle;
    }
    </style>
    """, unsafe_allow_html=True)

# ==================== LOGIN SECTION ====================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    with st.sidebar:
        st.subheader("Scan QR Code")
        try:
            st.image("QR code.png", caption="Scan to access the promotion")
        except Exception as e:
            st.error(f"Error loading QR code: {str(e)}")
    
    st.title("Please Provide Your Details to View the Promotion")
    with st.form("login_form"):
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email Address")
        company = st.text_input("Company Name")
        submitted = st.form_submit_button("View promotion")
        
        if submitted:
            if not (first_name.strip() and last_name.strip() and email.strip() and company.strip()):
                st.error("All fields are required.")
            else:
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    users_data = conn.read()
                    email_exists = False
                    if users_data is not None:
                        if isinstance(users_data, pd.DataFrame):
                            if email.strip().lower() in users_data["Email"].str.lower().values:
                                email_exists = True
                        else:
                            for row in users_data:
                                if row.get("Email", "").strip().lower() == email.strip().lower():
                                    email_exists = True
                                    break
                    if not email_exists:
                        new_entry = pd.DataFrame([{
                            "First Name": first_name.strip(),
                            "Last Name": last_name.strip(),
                            "Email": email.strip(),
                            "Company": company.strip()
                        }])
                        existing_data = users_data if isinstance(users_data, pd.DataFrame) else pd.DataFrame(users_data)
                        updated_data = pd.concat([existing_data, new_entry], ignore_index=True)
                        conn.update(data=updated_data)
                except Exception as e:
                    st.error(f"Error connecting to Google Sheets: {str(e)}")
                    st.stop()
                
                st.session_state.logged_in = True
                st.rerun()
    st.stop()

# ==================== MAIN APPLICATION ====================

# ------------------------- Promotion Header -------------------------
st.markdown('<div class="promo-header"><h1>Annual Promotion</h1></div>', unsafe_allow_html=True)

# ------------------------- Load Product Data -------------------------
csv_file = "model-export 20-02-25.csv"
df = pd.read_csv(csv_file)
df = df.dropna(subset=["Category", "Series"])

# ------------------------- Load Series Data with Images -------------------------
try:
    series_df = pd.read_csv("series.csv")
    series_images = {}
    for _, row in series_df.iterrows():
        series_name = row['Series name']
        image_url = row['Featured image']
        if pd.notna(series_name) and pd.notna(image_url):
            series_images[str(series_name).strip()] = str(image_url).strip()
except Exception as e:
    st.warning(f"Could not load series images: {str(e)}")
    series_images = {}

# ------------------------- Product Lifecycle Segmentation -------------------------
if "Product life cycle" in df.columns:
    lifecycle_values = ["All"] + sorted(df["Product life cycle"].dropna().unique().tolist())
else:
    lifecycle_values = ["All"]
    st.warning("'Product life cycle' column not found in the dataset.")

selected_lifecycle = st.segmented_control(
    label="Product Life Cycle",
    options=lifecycle_values,
    default="All"
)
if selected_lifecycle != "All" and "Product life cycle" in df.columns:
    df = df[df["Product life cycle"] == selected_lifecycle].copy()

# ------------------------- Sidebar Filters -------------------------
# Product Group Filter (displayed on top)
if "Product Group" in df.columns:
    product_groups = sorted(df["Product Group"].dropna().unique())
    selected_product_group = st.sidebar.selectbox("Select Product Group", options=["All Product Groups"] + product_groups)
    if selected_product_group != "All Product Groups":
        df = df[df["Product Group"] == selected_product_group].copy()
else:
    st.sidebar.info("No 'Product Group' column found in the dataset.")

# Category Filter
all_categories = sorted(df["Category"].dropna().unique())
selected_category = st.sidebar.selectbox("Select Category", options=["All Categories"] + all_categories)
if selected_category != "All Categories":
    filtered_df = df[df["Category"] == selected_category].copy()
else:
    filtered_df = df.copy()

# Series Filter based on (possibly) category–filtered data.
available_series = sorted(filtered_df["Series"].dropna().unique())
selected_series = st.sidebar.multiselect("Select Series", options=available_series, default=[], 
                                           help="Select one or more series to filter products")
if selected_series:
    filtered_df = filtered_df[filtered_df["Series"].isin(selected_series)]

# ------------------------- Specification Filters -------------------------
# This block both displays the available specification filters based on the narrowed set
# and shows the number of active spec filters (with a button to clear them)
if selected_category != "All Categories":
    st.sidebar.subheader("Specification Filters")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        applied_filter_count_placeholder = st.empty()  # We'll update the applied filter count below.
    with col2:
        clear_button = st.button("Clear Specification Filters")
        if clear_button:
            # Remove session_state keys that begin with "spec_filter_" or "spec_filter_checkbox_"
            for key in list(st.session_state.keys()):
                if key.startswith("spec_filter_") or key.startswith("spec_filter_checkbox_"):
                    del st.session_state[key]
            st.rerun()

    # Use a working copy so widgets recalc their available values based on current filters.
    working_df = filtered_df.copy()
    applied_filter_count = 0
    spec_columns = sorted([col for col in filtered_df.columns if ";" in col])
    
    for spec_col in spec_columns:
        # Only display a spec filter if at least one row in working_df has a non-null value.
        if not working_df[spec_col].notna().any():
            continue
        
        parts = spec_col.split(";", 1)
        spec_name = parts[0].strip()
        spec_type = parts[1].strip().lower()
        
        # For list-of-values type filters.
        if spec_type == "lov":
            values_set = set()
            for cell in working_df[spec_col].dropna():
                for v in str(cell).split(";"):
                    clean_val = v.strip()
                    if clean_val:
                        values_set.add(clean_val)
            options_list = sorted(values_set)
            if options_list:
                selected_options = st.sidebar.multiselect(
                    f"{spec_name} (LOV)",
                    options=options_list,
                    key=f"spec_filter_{spec_col}",
                    default=st.session_state.get(f"spec_filter_{spec_col}", [])
                )
                if selected_options:
                    applied_filter_count += 1
                    working_df = working_df[working_df[spec_col].apply(
                        lambda cell: bool(set(v.strip() for v in str(cell).split(";") if v.strip()) & set(selected_options))
                        if pd.notna(cell) else False)]
                    
        # For "number" type filters.
        elif spec_type == "number":
            pattern_number = re.compile(r'^\s*(-?\d+(?:\.\d+)?)(.*)$')
            number_list = []
            si_unit = ""
            for cell in working_df[spec_col].dropna():
                m = pattern_number.match(str(cell))
                if m:
                    try:
                        value = float(m.group(1))
                        number_list.append(value)
                        if not si_unit:
                            unit_candidate = m.group(2).strip()
                            if unit_candidate:
                                si_unit = unit_candidate
                    except Exception:
                        continue
            if number_list:
                global_min = min(number_list)
                global_max = max(number_list)
                label = f"{spec_name} (number"
                if si_unit:
                    label += f", {si_unit}"
                label += ")"
                apply_filter = st.sidebar.checkbox(
                    f"Filter by {label}",
                    key=f"spec_filter_checkbox_{spec_col}"
                )
                if apply_filter:
                    # If there is only one unique number, simply display that value.
                    if global_min == global_max:
                        st.sidebar.write(f"{spec_name}: {global_min}")
                        selected_range = (global_min, global_max)
                    else:
                        default_range = st.session_state.get(f"spec_filter_{spec_col}", (global_min, global_max))
                        selected_range = st.sidebar.slider(
                            f"{spec_name} (number)",
                            min_value=global_min,
                            max_value=global_max,
                            value=default_range,
                            key=f"spec_filter_{spec_col}"
                        )
                    applied_filter_count += 1
                    def match_number(cell):
                        if pd.isna(cell):
                            return False
                        try:
                            m = pattern_number.match(str(cell))
                            if m:
                                num_val = float(m.group(1))
                                return selected_range[0] <= num_val <= selected_range[1]
                            return False
                        except Exception:
                            return False
                    working_df = working_df[working_df[spec_col].apply(match_number)]
        
        # For "logical" type filters.
        elif spec_type == "logical":
            default_logic = st.session_state.get(f"spec_filter_{spec_col}", "Any")
            logical_choice = st.sidebar.radio(
                f"{spec_name} (logical)",
                options=["Any", "True", "False"],
                index=["Any", "True", "False"].index(default_logic) if default_logic in ["Any", "True", "False"] else 0,
                key=f"spec_filter_{spec_col}"
            )
            if logical_choice != "Any":
                applied_filter_count += 1
                working_df = working_df[working_df[spec_col].apply(
                    lambda cell: str(cell).strip().lower() == logical_choice.lower() if pd.notna(cell) else False)]
        
        # For "range" type filters.
        elif spec_type == "range":
            range_pattern = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)(.*)$')
            range_list = []
            for cell in working_df[spec_col].dropna():
                m = range_pattern.match(str(cell))
                if m:
                    try:
                        low = float(m.group(1))
                        high = float(m.group(2))
                        if low > high:
                            low, high = high, low
                        range_list.append((low, high))
                    except Exception:
                        continue
            if range_list:
                global_min = min(t[0] for t in range_list)
                global_max = max(t[1] for t in range_list)
                si_unit = ""
                for cell in working_df[spec_col].dropna():
                    m = range_pattern.match(str(cell))
                    if m:
                        unit_candidate = m.group(3).strip()
                        if unit_candidate:
                            si_unit = unit_candidate
                            break
                label = f"{spec_name} (range"
                if si_unit:
                    label += f", {si_unit}"
                label += ")"
                apply_range = st.sidebar.checkbox(
                    f"Filter by {label}",
                    key=f"spec_filter_checkbox_{spec_col}"
                )
                if apply_range:
                    if global_min == global_max:
                        st.sidebar.write(f"{spec_name}: Only value {global_min}")
                        selected_vals = (global_min, global_max)
                    else:
                        default_range = st.session_state.get(f"spec_filter_{spec_col}", (global_min, global_max))
                        selected_vals = st.sidebar.slider(
                            f"{spec_name} (range)",
                            min_value=global_min,
                            max_value=global_max,
                            value=default_range,
                            key=f"spec_filter_{spec_col}"
                        )
                    applied_filter_count += 1
                    def match_range(cell):
                        if pd.isna(cell):
                            return False
                        try:
                            m = range_pattern.match(str(cell))
                            if m:
                                low = float(m.group(1))
                                high = float(m.group(2))
                                return (high >= selected_vals[0]) and (low <= selected_vals[1])
                            return False
                        except Exception:
                            return False
                    working_df = working_df[working_df[spec_col].apply(match_range)]
    
    applied_filter_count_placeholder.markdown(f"Applied Specification Filters: {applied_filter_count}")
    st.sidebar.markdown(f"Models Displayed: {len(working_df)}")
    filtered_df = working_df.copy()  # use the narrowed working_df for display.
else:
    st.sidebar.info("Select a specific category to filter specifications further.")

# ------------------------- Main Content: Group and Display Products -------------------------
if filtered_df.empty:
    st.info("No products found with the current filters.")
else:
    for category, cat_data in filtered_df.groupby("Category", sort=False):
        st.markdown(f'<div class="section-header"><h2>Category: {category}</h2></div>', unsafe_allow_html=True)
        for series, series_data in cat_data.groupby("Series", sort=False):
            series_image_html = ""
            if series in series_images:
                series_image_html = f'<img src="{series_images[series]}" class="series-image" alt="{series}">'
            st.markdown(f'''
                <div class="subsection-header">
                    {series_image_html}
                    <h3>Series: {series}</h3>
                </div>
            ''', unsafe_allow_html=True)
            
            for idx, row in series_data.iterrows():
                lifecycle_info = ""
                if "Product life cycle" in row and pd.notna(row["Product life cycle"]):
                    lifecycle_info = f'<p><strong>Lifecycle:</strong> {row["Product life cycle"]}</p>'
                buy_url = f"https://store.omron.com.au/product/{row['SKU']}"
                details_html = f"""
<details>
  <summary>
    <div>
      <h5>{row['Name']}</h5>
      <p><strong>Description:</strong> {row['Description']}</p>
      <p><strong>Price:</strong> ${row['Sale price in Australia']}</p>
      {lifecycle_info}
      <a href="{buy_url}" target="_blank">
         <button class="buy-button">Buy Now</button>
      </a>
    </div>
  </summary>
  <div style="margin-top: 10px;">
"""
                if pd.notna(row["Featured image"]):
                    details_html += f'<img src="{row["Featured image"]}" width="200" alt="Product Image">'
                else:
                    details_html += "<p>No image available</p>"
                details_html += f'<p><strong>SKU:</strong> {row["SKU"]}</p>'
                details_html += "</div></details>"
                st.markdown(details_html, unsafe_allow_html=True)

# ------------------------- Hide Streamlit Menu -------------------------
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)