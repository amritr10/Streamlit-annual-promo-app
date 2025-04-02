#!/usr/bin/env python
import streamlit as st
import pandas as pd
import re
from streamlit_gsheets import GSheetsConnection

# ------------------------- Helper Functions -------------------------
def reset_all_filters():
    """Reset all filter-related keys and rerun the app.
       Also resets the view mode and selected product group to their default values.
    """
    reset_keys = [
        "search_query", "search_bar_input",
        "selected_category", "selected_product_group",
        "selected_series", "selected_lifecycle"
    ]
    for key in list(st.session_state.keys()):
        if (key in reset_keys or
            key.startswith("spec_filter_") or
            key.startswith("spec_filter_checkbox_")):
            del st.session_state[key]

    # Explicitly reset the Product Group to its default value
    st.session_state["selected_product_group"] = "All Product Groups"
    st.session_state["view_mode"] = "Table View"
    st.rerun()

def search_callback():
    """When the user presses ENTER in the search input:
       • Save the input text in 'search_query'
       • Clear the text input.
    """
    if st.session_state.get("search_bar_input", "").strip():
        st.session_state.search_query = st.session_state.search_bar_input.strip()
        st.session_state.search_bar_input = ""

# ------------------------- YouTube Thumbnail Utility -------------------------
def get_youtube_thumbnail(url):
    """Extracts the video id from a YouTube URL and returns the URL for its thumbnail image."""
    video_id = None
    watch_match = re.search(r"v=([^&]+)", url)
    if watch_match:
        video_id = watch_match.group(1)
    else:
        short_match = re.search(r"youtu\.be/([^?&]+)", url)
        if short_match:
            video_id = short_match.group(1)
    if video_id:
        return f"https://img.youtube.com/vi/{video_id}/0.jpg"
    return None

# ------------------------- Page Setup -------------------------
st.set_page_config(page_title="Key Products 2025", layout="wide")

# ------------------------- Custom CSS -------------------------
st.markdown("""
    <style>
    /* Pulse effect on details hover */
    @keyframes pulse {
         0% { transform: scale(1); }
         50% { transform: scale(1.02); }
         100% { transform: scale(1); }
    }
    details:hover {
         border-color: #ADD8E6 !important;
         border-radius: 20px;
         border-width: 5px;
         animation: pulse 1s forwards;
    }
    /* Product titles inside details are navy blue */
    [data-testid="stHeadingWithActionElements"],
    details summary h5 {
         color: #000080;
    }
    /* Pricing in green */
    .price {
         color: green;
         font-weight: bold;
    }
    /* Specification filter container: its labels will be navy blue */
    [data-testid="stMarkdownContainer"],
    .spec-filter-container label {
         color: #000080 !important;
    }
    /* Each specification filter item gets its own border and padding */
    .spec-filter-item {
         border: 1px solid #000000;
         border-radius: 1px;
         background-color: #ffffff;
    }
    /* Dropdown expanders (product group, category, series) get light blue styling */
    [data-baseweb="select"],
    [data-testid="stSidebarContent"] {
         background-color: #f2f2f2 !important;
         border-color: #000080 !important;
         color: #000080 !important;
    }
    /* Promotion header styles */
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
    /* Section header (for categories) */
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
    /* Series subsection header */
    .subsection-header {
        padding: 5px 10px;
        background-color: #f8f9fa;
        border-left: 4px solid #d6336c;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
    }
    .series-info {
        margin-left: 10px;
    }
    .series-info h3 {
        margin: 0;
        color: #495057;
    }
    .series-info p {
        margin: 0;
        font-size: 0.9em;
        color: #6c757d;
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
        width: 100px;
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
            st.image("QR code.png", caption="Scan to access the promotion on mobile")
        except Exception as e:
            st.error(f"Error loading QR code: {str(e)}")
    st.title("Please Provide Your Details to View the Promotion")
    with st.form("login_form"):
        first_name = st.text_input("First Name")
        last_name  = st.text_input("Last Name")
        email      = st.text_input("Email Address")
        company    = st.text_input("Company Name")
        submitted  = st.form_submit_button("View promotion")
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
st.markdown('<div class="promo-header"><h1>Key Products 2025</h1></div>', unsafe_allow_html=True)

# ------------------------- Load Product Data -------------------------
csv_file = "model-export 20-02-25.csv"
df = pd.read_csv(csv_file)
df = df.dropna(subset=["Category", "Series"])

# ------------------------- Load Series Data with Images and Descriptions -------------------------
try:
    series_df = pd.read_csv("series.csv")
    series_images = {}
    series_descriptions = {}
    for _, row in series_df.iterrows():
        series_name = row.get('Series name', None)
        image_url   = row.get('Featured image', None)
        description = row.get('Description', None)
        if pd.notna(series_name):
            key = str(series_name).strip()
            if pd.notna(image_url):
                series_images[key] = str(image_url).strip()
            if pd.notna(description):
                series_descriptions[key] = str(description).strip()
except Exception as e:
    st.warning(f"Could not load series images or descriptions: {str(e)}")
    series_images = {}
    series_descriptions = {}

# ------------------------- Product Lifecycle Segmentation, Search & Sorting -------------------------
if "Product life cycle" in df.columns:
    lifecycle_values = ["All"] + sorted(df["Product life cycle"].dropna().unique().tolist())
else:
    lifecycle_values = ["All"]
    st.warning("'Product life cycle' column not found in the dataset.")

# ---- Top Row: Lifecycle Filter, Search Bar and Reset Buttons, Sort Dropdown ----
col1, col2, col3 = st.columns([3, 4, 1])
with col1:
    selected_lifecycle = st.segmented_control(
         label="Product Life Cycle",
         options=lifecycle_values,
         default="All",
         key="selected_lifecycle"
    )
with col2:
    st.text_input(
         "Search Model Name", 
         key="search_bar_input",
         on_change=search_callback,
         help="Enter a part or the full name of the model and press Enter"
    )
    if st.session_state.get("search_query", ""):
         msg_cols = st.columns([0.9, 0.1])
         with msg_cols[0]:
              st.markdown(f"**Models searched for:** {st.session_state.search_query}")
         with msg_cols[1]:
              if st.button("❌", key="clear_search_btn"):
                   del st.session_state.search_query
                   st.session_state["view_mode"] = "Table View"
                   st.rerun()
with col3:
    sort_option = st.selectbox(
         "Sort", 
         options=["Price: Low to High", "Price: High to Low", "Name: A to Z", "Name: Z to A"]
    )

# ------------------------- Apply Filters -------------------------
if selected_lifecycle != "All" and "Product life cycle" in df.columns:
    df = df[df["Product life cycle"] == selected_lifecycle].copy()

if st.session_state.get("search_query", "").strip():
    search_term = st.session_state.search_query.strip()
    df = df[df["Name"].str.contains(search_term, case=False, na=False)].copy()

# ------------------------- Sidebar Filters -------------------------
reset_condition_sidebar = (
    st.session_state.get("search_query", "") != "" or
    st.session_state.get("selected_category", "All Categories") != "All Categories" or
    st.session_state.get("selected_product_group", "All Product Groups") != "All Product Groups" or
    st.session_state.get("selected_series", []) or
    st.session_state.get("selected_lifecycle", "All") != "All"
)
if reset_condition_sidebar:
    if st.sidebar.button("Reset All Filters", key="reset_button_sidebar"):
         reset_all_filters()

if "Product Group" in df.columns:
    product_groups = sorted(df["Product Group"].dropna().unique())
    selected_product_group = st.sidebar.selectbox(
         "Select Product Group", 
         options=["All Product Groups"] + product_groups,
         key="selected_product_group"
    )
    if selected_product_group != "All Product Groups":
        df = df[df["Product Group"] == selected_product_group].copy()
else:
    st.sidebar.info("No 'Product Group' column found in the dataset.")

all_categories = sorted(df["Category"].dropna().unique())
selected_category = st.sidebar.selectbox(
    "Select Category", 
    options=["All Categories"] + all_categories, 
    key="selected_category"
)
if selected_category != "All Categories":
    filtered_df = df[df["Category"] == selected_category].copy()
else:
    filtered_df = df.copy()
    
available_series = sorted(filtered_df["Series"].dropna().unique())
selected_series = st.sidebar.multiselect(
    "Select Series", 
    options=available_series, 
    default=[], 
    key="selected_series",
    help="Select one or more series to filter products"
)
if selected_series:
    filtered_df = filtered_df[filtered_df["Series"].isin(selected_series)]

# ------------------------- Specification Filters -------------------------
if selected_category != "All Categories":
    st.sidebar.markdown('<div class="spec-filter-container">', unsafe_allow_html=True)
    models_displayed_placeholder = st.empty()
    models_displayed_placeholder.markdown(f"Models Displayed: {len(filtered_df)}")
    st.sidebar.subheader("Specification Filters")
    col1_filter, col2_filter = st.sidebar.columns(2)
    with col1_filter:
        applied_filter_count_placeholder = st.empty()
    with col2_filter:
        clear_button = st.button("Clear Specification Filters")
        if clear_button:
            for key in list(st.session_state.keys()):
                if key.startswith("spec_filter_") or key.startswith("spec_filter_checkbox_"):
                    del st.session_state[key]
            st.session_state["view_mode"] = "Table View"
            st.rerun()
    working_df = filtered_df.copy()
    applied_filter_count = 0
    spec_columns = sorted([col for col in filtered_df.columns if ";" in col])
    for spec_col in spec_columns:
        if not working_df[spec_col].notna().any():
            continue
        st.sidebar.markdown('<div class="spec-filter-item">', unsafe_allow_html=True)
        parts = spec_col.split(";", 1)
        spec_name = parts[0].strip()
        spec_type = parts[1].strip().lower()
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
                        lambda cell: bool({v.strip() for v in str(cell).split(";") if v.strip()} & set(selected_options))
                        if pd.notna(cell) else False)]
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
        st.sidebar.markdown('</div>', unsafe_allow_html=True)
    applied_filter_count_placeholder.markdown(f"Applied Specification Filters: {applied_filter_count}")
    models_displayed_placeholder.markdown(f"Models Displayed: {len(working_df)}")
    filtered_df = working_df.copy()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)
else:
    st.sidebar.info("Select a specific category to filter specifications further.")

# ------------------------- Sorting the Final Products -------------------------
if sort_option in ["Price: Low to High", "Price: High to Low"]:
    if "Sale price in Australia" in filtered_df.columns:
        filtered_df["Sale price in Australia"] = pd.to_numeric(filtered_df["Sale price in Australia"], errors="coerce")
        if sort_option == "Price: Low to High":
            filtered_df = filtered_df.sort_values(by="Sale price in Australia", ascending=True)
        else:
            filtered_df = filtered_df.sort_values(by="Sale price in Australia", ascending=False)
elif sort_option in ["Name: A to Z", "Name: Z to A"]:
    if "Name" in filtered_df.columns:
        if sort_option == "Name: A to Z":
            filtered_df = filtered_df.sort_values(by="Name", ascending=True)
        else:
            filtered_df = filtered_df.sort_values(by="Name", ascending=False)

# ------------------------- View Mode Switcher -------------------------
# If the "New Product" life cycle is selected, include a third option.
if selected_lifecycle == "New Product":
    display_options = ["Expander View", "Table View", "Product Experience View"]
else:
    display_options = ["Expander View", "Table View"]

default_view = "Table View" if "Table View" in display_options else display_options[0]
view_mode = st.radio("Display Options", options=display_options, index=display_options.index(default_view), key="view_mode")

# ------------------------- Main Content: New Product Experience View or Original -------------------------
if filtered_df.empty:
    st.info("No products found with the current filters.")
else:
    # If the New Product life cycle is selected and the Product Experience View is active,
    # then show a special new product experience display.
    if selected_lifecycle == "New Product" and view_mode == "Product Experience View":
        # Use st.pills to choose the series for the experience view instead of st.radio.
        new_series_list = sorted(filtered_df["Series"].dropna().unique())
        if new_series_list:
            selected_series_exp = st.pills("Select Series for New Product Experience", options=new_series_list, key="exp_new_series")
            # Look up metadata from series.csv for the selected Series.
            series_info_df = series_df[series_df["Series name"].str.strip() == selected_series_exp]
            if series_info_df.empty:
                st.error("Series information not found in series.csv for the selected series.")
            else:
                series_info = series_info_df.iloc[0]
                # ----- Section 1: Series Header & Image -----
                st.markdown("---")
                col1_sec1, col2_sec1 = st.columns([3, 1])
                with col1_sec1:
                    st.title(series_info.get("Series name", ""))
                    st.header(series_info.get("Short description", ""))
                    st.write(series_info.get("Description", ""))
                with col2_sec1:
                    if pd.notna(series_info.get("Featured image", "")):
                        st.image(series_info["Featured image"], width=400)
                    else:
                        st.write("No image available")
                # ----- Section 2: Products Table -----
                st.markdown("---")
                st.header("Products")
                exp_products_df = filtered_df[filtered_df["Series"]==selected_series_exp].copy()
                if not exp_products_df.empty:
                    exp_products_df["Buy URL"] = exp_products_df["SKU"].apply(
                         lambda sku: "https://store.omron.com.au/product/" + re.sub(r"\s+", "-", sku.strip())
                    )
                    def format_price(x):
                        try:
                            return f"${float(x):.2f}"
                        except Exception:
                            return x
                    if "Sale price in Australia" in exp_products_df.columns:
                        exp_products_df["Sale price in Australia"] = exp_products_df["Sale price in Australia"].apply(format_price)
                    cols_to_show = ["Name", "Description", "Sale price in Australia", "Promo Catalogue Print?", "Buy URL"]
                    cols_to_show = [col for col in cols_to_show if col in exp_products_df.columns]
                    st.table(exp_products_df[cols_to_show].reset_index(drop=True))
                else:
                    st.info("No products found for the selected series.")
                # ----- Section 3: Features -----
                st.markdown("---")
                st.header("Features")
                col1_sec3, col2_sec3 = st.columns([3, 1])
                with col1_sec3:
                    st.title(series_info.get("Feature set header 1", ""))
                    st.write(series_info.get("Feature set description 1", ""))
                with col2_sec3:
                    if pd.notna(series_info.get("Feature set image 1", "")):
                        st.image(series_info["Feature set image 1"], width=500)
                    else:
                        st.write("No feature image available")
                # ----- Section 4: Videos -----
                st.markdown("---")
                st.header("Videos")
                video_url = series_info.get("Video 1", "")
                if video_url and video_url.strip() != "":
                    thumbnail_url = get_youtube_thumbnail(video_url)
                    if thumbnail_url:
                        st.image(thumbnail_url, width=400)
                        st.markdown(f"[Watch Video]({video_url})")
                    else:
                        st.write("Invalid video URL")
                else:
                    st.info("No video available")
                # ----- Section 5: Downloads -----
                st.markdown("---")
                st.header("Downloads")
                # Use st.pills to choose the download type
                download_option = st.pills("Select download type", 
                                           options=["Datasheet link", "<Manual.|Node|.AWS Deep Link - Original>"],
                                           key="downloads_selector")
                if not exp_products_df.empty:
                    download_links = []
                    for idx, row in exp_products_df.iterrows():
                        link = row.get(download_option, "")
                        if pd.notna(link) and link.strip() != "":
                            download_links.append((row.get("Name", "Product"), link.strip()))
                    if download_links:
                        for name, link in download_links:
                            st.markdown(f"- [{name}]({link})")
                    else:
                        st.info("No download links available")
                else:
                    st.info("No products to download.")
        else:
            st.info("No series available for New Product experience.")
    else:
        # ---- Original Display: Group products by Category and then Series (Expander or Table View) ----
        for category, cat_data in filtered_df.groupby("Category", sort=False):
            st.markdown(f'<div class="section-header"><h2>Category: {category}</h2></div>', unsafe_allow_html=True)
            for series, series_data in cat_data.groupby("Series", sort=False):
                series_image_html = ""
                if series in series_images:
                    series_image_html = f'<img src="{series_images[series]}" class="series-image" alt="{series}">'
                desc_html = ""
                if series in series_descriptions:
                    desc_html = f'<p>{series_descriptions[series]}</p>'
                st.markdown(f'''
                    <div class="subsection-header">
                        {series_image_html}
                        <div class="series-info">
                            <h3>Series: {series}</h3>
                            {desc_html}
                        </div>
                    </div>
                ''', unsafe_allow_html=True)
                if view_mode == "Expander View":
                    for idx, row in series_data.iterrows():
                        sku_clean = re.sub(r'\s+', '-', row["SKU"].strip())
                        buy_url = f"https://store.omron.com.au/product/{sku_clean}"
                        details_html = f"""
<details>
  <summary>
    <div>
      <h5>{row['Name']}</h5>
      <p><strong>Description:</strong> {row['Description']}</p>
      <p><strong>Price:</strong> <span class="price">${row['Sale price in Australia']}</span></p>
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
                else:  # Table View
                    table_df = series_data.copy()
                    table_df["Buy URL"] = table_df["SKU"].apply(
                        lambda sku: "https://store.omron.com.au/product/" + re.sub(r"\s+", "-", sku.strip())
                    )
                    def format_price(x):
                        try:
                            return f"${float(x):.2f}"
                        except Exception:
                            return x
                    if "Sale price in Australia" in table_df.columns:
                        table_df["Sale price in Australia"] = table_df["Sale price in Australia"].apply(format_price)
                    cols_to_show = ["Name", "Description", "Sale price in Australia", "Promo Catalogue Print?", "Buy URL"]
                    cols_to_show = [col for col in cols_to_show if col in table_df.columns]
                    st.table(table_df[cols_to_show].reset_index(drop=True))

# ------------------------- Hide Streamlit Menu -------------------------
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)
