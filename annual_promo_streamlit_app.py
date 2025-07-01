#!/usr/bin/env python
import streamlit as st
import pandas as pd
import re
import streamlit.components.v1 as components
from streamlit_gsheets import GSheetsConnection
import os
import glob
import json
from datetime import datetime

# ------------------------- Helper Functions -------------------------
def reset_all_filters():
    """Reset all filter-related keys and rerun the app.
       Also resets the view mode and selected product group to their default values.
    """
    reset_keys = [
        "search_query", "search_bar_input",
        "selected_category", "selected_product_group",
        "selected_series", "selected_lifecycle","promo_catalogue_filter"
    ]
    for key in list(st.session_state.keys()):
        if (key in reset_keys or
            key.startswith("spec_filter_") or
            key.startswith("spec_filter_checkbox_")):
            del st.session_state[key]

    # Explicitly reset the Product Group to its default value
    st.session_state["selected_product_group"] = "All Product Groups"
    st.session_state["selected_category"] = "All Categories"
    st.session_state["view_mode"] = "Table View"
    st.session_state["promo_catalogue_filter"] = False
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

# ------------------------- Bundle Network Helpers -------------------------
def filter_and_sum(df, search_terms, exclusion_terms=None,
                   column_name='Description', sum_columns=[]):
    """Filter by wildcard search_terms (+ exclusions), sum specified columns."""
    def pattern(t):
        return '^' + re.escape(t.strip()).replace(r'\*','.*') + '$'
    pats = [pattern(t) for t in search_terms if t.strip()]
    if not pats:
        return df.iloc[0:0].copy(), {c:0.0 for c in sum_columns}
    rx = re.compile("|".join(pats), flags=re.IGNORECASE)
    mask = df[column_name].astype(str).str.match(rx)
    if exclusion_terms:
        ex_pats = [pattern(t) for t in exclusion_terms if t.strip()]
        if ex_pats:
            ex_rx = re.compile("|".join(ex_pats), flags=re.IGNORECASE)
            mask &= ~df[column_name].astype(str).str.match(ex_rx)
    sub = df[mask].copy()
    sums = {c: float(sub[c].sum()) if c in sub else 0.0 for c in sum_columns}
    return sub, sums

def flatten_mappings(mappings_data, mapping_to_parent, dependent_sums=None):
    """Turn mappings_data into a flat DataFrame for graph construction."""
    rows = []
    for mg, df_m in mappings_data.items():
        pg = mapping_to_parent.get(mg,"")
        for _, r in df_m.iterrows():
            dg = r['Dependent Group']
            rows.append({
                "Parent Group": pg,
                "Dependent Group": dg,
                "Type": r['Type'],
                "Multiple": float(r['Multiple'])
            })
    return pd.DataFrame(rows)

def build_network_dot(flat_df):
    """Produce a Graphviz dot string from the flat mapping DataFrame."""
    dot = ["digraph G {", "  rankdir=LR;"]
    for pg in flat_df['Parent Group'].unique():
        dot.append(f'  "{pg}" [shape=box, style=filled, fillcolor=lightblue];')
    for dg in flat_df['Dependent Group'].unique():
        dot.append(f'  "{dg}" [shape=ellipse, style=filled, fillcolor=lightgreen];')
    for _, r in flat_df.iterrows():
        style = "solid" if r['Type']=="Objective" else "dashed"
        color = "blue"   if r['Type']=="Objective" else "gray"
        dot.append(
          f'  "{r["Parent Group"]}" -> "{r["Dependent Group"]}" '
          f'[label="{r["Type"]} ({r["Multiple"]})", style="{style}", color="{color}"];'
        )
    dot.append("}")
    return "\n".join(dot)

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
        # ---- New: Password Field ----
        password   = st.text_input("Password", type="password", help="Enter the promotion password")
        submitted  = st.form_submit_button("View promotion")
        if submitted:
            # 1) basic required‐fields check
            if not (first_name.strip() and last_name.strip()
                    and email.strip() and company.strip() 
                    and password.strip()):
                st.error("All fields are required.")
                st.stop()

            # 2) domain‐check
            allowed_domains = [
                "@omron.com"
            ]
            email_clean = email.strip().lower()
            if not any(email_clean.endswith(d) for d in allowed_domains):
                st.error(
                f"You're not allowed to access this. "
                f"Please contact Amrit"
                )
                st.stop()

            # 3) password‐check
            if password.strip() != "au$promo2025":
                st.error("Incorrect password. Please try again.")
                st.stop()

            # 4) at this point, both domain & password are good → record login time
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 5) read & normalize your sheet data into a DataFrame
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                raw = conn.read()  # could be DataFrame or list-of-dicts or None
                if raw is None:
                    users_df = pd.DataFrame(columns=[
                        "First Name","Last Name","Email","Company","Last login"
                    ])
                elif isinstance(raw, pd.DataFrame):
                    users_df = raw.copy()
                else:
                    users_df = pd.DataFrame(raw)

                # ensure the “Last login” column exists
                if "Last login" not in users_df.columns:
                    users_df["Last login"] = ""

                # 6) find existing row (case‐insensitive match)
                mask = users_df["Email"].str.lower() == email_clean
                if mask.any():
                    # update their timestamp
                    users_df.loc[mask, "Last login"] = now
                else:
                    # append a new record
                    new_row = {
                        "First Name": first_name.strip(),
                        "Last Name" : last_name.strip(),
                        "Email"     : email.strip(),
                        "Company"   : company.strip(),
                        "Last login": now
                    }
                    users_df = pd.concat([users_df, pd.DataFrame([new_row])],
                                        ignore_index=True)

                # 7) write the sheet back
                conn.update(data=users_df)

            except Exception as e:
                st.error(f"Error connecting to Google Sheets: {e}")
                st.stop()

            # finally, mark them logged in & rerun
            st.session_state.logged_in = True
            st.rerun()
    st.stop()

# ==================== MAIN APPLICATION ====================

# ------------------------- Promotion Header -------------------------
st.markdown('<div class="promo-header"><h1>Key Products 2025</h1></div>', unsafe_allow_html=True)
st.markdown('<div class="proof of concept, internal use"><h2>This website is a proof of concept, internal use only</h2></div>', unsafe_allow_html=True)

# ------------------------- Load Product Data -------------------------
csv_file = "key_products_12_05_25.csv"
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

# ――――――― Dynamic Category ↔ Series linkage ―――――――
picked_series = st.session_state.get("selected_series", [])

# 1) figure out which categories those series live in (if any)
if picked_series:
    cats_for_series = (
        df[df["Series"].isin(picked_series)]
          ["Category"]
          .dropna()
          .unique()
          .tolist()
    )
    cats_for_series.sort()
else:
    cats_for_series = None

# 2) decide what to show in the Category dropdown
if cats_for_series is None:
    category_options = sorted(df["Category"].dropna().unique())
else:
    category_options = cats_for_series

# 3) if the user has picked series but their current category
#    isn’t one of the cats_for_series, auto-sync:
cur_cat = st.session_state.get("selected_category", "All Categories")
if cats_for_series:
    if cur_cat not in cats_for_series:
        if len(cats_for_series) == 1:
            st.session_state["selected_category"] = cats_for_series[0]
        else:
            st.session_state["selected_category"] = "All Categories"

# 4) render the Category selector
selected_category = st.sidebar.selectbox(
    "Select Category",
    options=["All Categories"] + category_options,
    key="selected_category"
)

# 5) if they’ve picked series across >1 category, force them to choose one
if cats_for_series and len(cats_for_series) > 1 and selected_category == "All Categories":
    st.sidebar.warning(
        "You’ve picked Series spanning multiple Categories.  "
        "Please choose a Category to unlock the spec-filters."
    )

# 6) now filter down by category
if selected_category != "All Categories":
    filtered_df = df[df["Category"] == selected_category].copy()
else:
    filtered_df = df.copy()

# 7) finally render your Series multiselect (it will pull from the filtered_df)
available_series = sorted(filtered_df["Series"].dropna().unique())
selected_series = st.sidebar.multiselect(
    "Select Series",
    options=available_series,
    key="selected_series",
    default=st.session_state.get("selected_series", []),
    help="Select one or more series to filter products"
)
if selected_series:
    filtered_df = filtered_df[filtered_df["Series"].isin(selected_series)].copy()
# ――――――― end Dynamic Category ↔ Series linkage ―――――――

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
    if "List Price" in filtered_df.columns:
        filtered_df["List Price"] = pd.to_numeric(filtered_df["List Price"], errors="coerce")
        if sort_option == "Price: Low to High":
            filtered_df = filtered_df.sort_values(by="List Price", ascending=True)
        else:
            filtered_df = filtered_df.sort_values(by="List Price", ascending=False)
elif sort_option in ["Name: A to Z", "Name: Z to A"]:
    if "Name" in filtered_df.columns:
        if sort_option == "Name: A to Z":
            filtered_df = filtered_df.sort_values(by="Name", ascending=True)
        else:
            filtered_df = filtered_df.sort_values(by="Name", ascending=False)

# ------------------------- View Mode and Promo Catalogue Filter Switcher -------------------------
if selected_lifecycle == "New Product":
    display_options = ["Expander View", "Table View", "Product Experience View"]
    default_view = "Product Experience View"
else:
    display_options = ["Expander View", "Table View"]
    default_view = "Table View"

# Place the Display Options on the left and the Promo Catalogue filter on the right.
view_col, promo_col = st.columns([3,1])
with view_col:
    view_mode = st.radio("Display Options", options=display_options, index=display_options.index(default_view), key="view_mode")
with promo_col:
    promo_filter = st.checkbox("Promo Catalogue Print?", key="promo_catalogue_filter", help="Show only products having ‘Promo Catalogue Print?’ as ✅")

# If the promo filter is active then limit the products further.
if promo_filter:
    if "Promo Catalogue Print?" in filtered_df.columns:
        filtered_df = filtered_df[filtered_df["Promo Catalogue Print?"].astype(str).str.strip() == "✅"]
    else:
        st.warning("The column 'Promo Catalogue Print?' was not found in the dataset.")

# ------------------------- Main Content: New Product Experience View or Original -------------------------
if filtered_df.empty:
    st.info("No products found with the current filters.")
else:
    # If the New Product life cycle is selected and the Product Experience View is active,
    # then show a special new product experience display.
    if selected_lifecycle == "New Product" and view_mode == "Product Experience View":
        new_series_list = sorted(filtered_df["Series"].dropna().unique())
        if new_series_list:
            selected_series_exp = st.pills("Select Series for New Product Experience", options=new_series_list, key="exp_new_series")
            series_info_df = series_df[series_df["Series name"].str.strip() == selected_series_exp]
            if series_info_df.empty:
                st.error("Select a product series above to explore its details, features, and specifications. Tap to enter the full product experience!")
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
                    if "List Price" in exp_products_df.columns:
                        exp_products_df["List Price"] = exp_products_df["List Price"].apply(format_price)
                    if "Distributor Price" in exp_products_df.columns:
                        exp_products_df["Distributor Price"] = exp_products_df["Distributor Price"].apply(format_price)
                    cols_to_show = ["Name", "Description", "List Price", "Distributor Price", "Promo Catalogue Print?", "Buy URL"]
                    cols_to_show = [col for col in cols_to_show if col in exp_products_df.columns]
                    display_df = exp_products_df.reset_index(drop=True)
                    st.table(display_df.head(10)[cols_to_show])
                    if len(display_df) > 10:
                        with st.expander("Show more"):
                            st.table(display_df.iloc[10:][cols_to_show])
                else:
                    st.info("No products found for the selected series.")

                # ----- Section 3: Features -----
                st.markdown("---")
                st.header("Features")
                feature_indices = []
                for col in series_info.index:
                    m = re.match(r"Feature set header (\d+)$", col)
                    if m:
                        feature_indices.append(int(m.group(1)))
                feature_indices.sort()
                for i, idx in enumerate(feature_indices):
                    header = series_info.get(f"Feature set header {idx}", "")
                    desc   = series_info.get(f"Feature set description {idx}", "")
                    img    = series_info.get(f"Feature set image {idx}", "")
                    header = header if pd.notna(header) else ""
                    desc   = desc if pd.notna(desc) else ""
                    img    = img if pd.notna(img) else ""
                    if header or desc or img:
                        if i % 2 == 0:
                            text_col, img_col = st.columns([3, 1])
                        else:
                            img_col, text_col = st.columns([1, 3])
                        with text_col:
                            st.subheader(header)
                            st.write(desc)
                        with img_col:
                            if img:
                                st.image(img, width=400)
                            else:
                                st.write("No feature image available")
                        st.markdown("---")

                # ----- Section 3.5: Bundle Network (REPLACED) -----
                st.markdown("---")
                st.subheader("Demo Bundle")

                # 1) load the JSON config for this series
                config_dir = "bundles config files"
                pattern    = os.path.join(config_dir, f"*{selected_series_exp}*.json")
                cfg_files  = glob.glob(pattern)
                if not cfg_files:
                    st.info(f"No bundle configuration found for series '{selected_series_exp}'.")
                    bundle_cfg = None
                else:
                    try:
                        with open(cfg_files[0], "r") as f:
                            bundle_cfg = json.load(f)
                    except Exception as e:
                        st.error(f"Failed to parse {cfg_files[0]}: {e}")
                        bundle_cfg = None

                if bundle_cfg:
                    # filter your products down to just this series
                    bundle_df = filtered_df[filtered_df["Series"] == selected_series_exp].copy()
                    bundle_df["_price"] = pd.to_numeric(bundle_df.get("Sale price in Australia",""), errors="coerce")

                    # 2) Build mappings_data & mapping_to_parent from _all_ parent_groups
                    mappings_data     = {}
                    mapping_to_parent = {}
                    for pg_cfg in bundle_cfg["parent_groups"]:
                        pg_name = pg_cfg["name"]
                        sel_block = bundle_cfg["mapping_selections"].get(pg_name, {})
                        mg_name   = sel_block.get("mapping_group_name", pg_name)
                        entries   = []
                        for dep in sel_block.get("selected_dependents", []):
                            entries.append({
                                "Dependent Group": dep["name"],
                                "Type": ("Objective" if dep.get("Objective Mapping",False) else "Subjective"),
                                "Multiple": float(dep.get("multiple",1.0))
                            })
                        if entries:
                            mappings_data[mg_name]     = pd.DataFrame(entries)
                            mapping_to_parent[mg_name] = pg_name

                    # 3) Build one selector per parent group
                    sel_parent    = {}
                    parent_dfs    = {}
                    for i, pg_cfg in enumerate(bundle_cfg["parent_groups"]):
                        pg_name = pg_cfg["name"]
                        dfp, _  = filter_and_sum(
                            bundle_df,
                            pg_cfg["search_terms"],
                            pg_cfg.get("exclusion_terms",[]),
                            column_name="Name",
                            sum_columns=[]
                        )
                        parent_dfs[pg_name] = dfp
                        opts = [f"{r.Name} – {r.Description}" for _,r in dfp.iterrows()]
                        opts = ["— select —"] + opts
                        lbl = st.selectbox(f"Select product for {pg_name}", opts, key=f"bundle_sel_parent_{i}")
                        sel_parent[pg_name] = None if lbl=="— select —" else lbl.split(" – ")[0]

                    # 4) Build one selector per dependent group
                    sel_dependent = {}
                    dependent_dfs = {}
                    for j, dg_cfg in enumerate(bundle_cfg["dependent_groups"]):
                        dg_name = dg_cfg["name"]
                        dfd, _  = filter_and_sum(
                            bundle_df,
                            dg_cfg["search_terms"],
                            dg_cfg.get("exclusion_terms",[]),
                            column_name="Name",
                            sum_columns=[]
                        )
                        dependent_dfs[dg_name] = dfd
                        opts = [f"{r.Name} – {r.Description}" for _,r in dfd.iterrows()]
                        opts = ["— select —"] + opts
                        lbl = st.selectbox(f"Select product for {dg_name}", opts, key=f"bundle_sel_dep_{j}")
                        sel_dependent[dg_name] = None if lbl=="— select —" else lbl.split(" – ")[0]

                    # 5) Collect your renames
                    rename_map = {}
                    for pg, sel in sel_parent.items():
                        if sel: rename_map[pg] = sel
                    for dg, sel in sel_dependent.items():
                        if sel: rename_map[dg] = sel

                    # 6) Flatten & draw one single graph (with type->label translation & multi-line node labels)
                    type_label_map = {
                        "Objective":  "Required",
                        "Subjective": "Optional"
                    }

                    # rebuild the flat_df as before
                    flat_df = flatten_mappings(mappings_data, mapping_to_parent)

                    if flat_df.empty:
                        st.info("No mappings to display for this series.")
                    else:
                        # start the graph
                        dot = [
                        "digraph G {",
                        "  rankdir=LR;",
                        "  node [fontname=\"Arial\"];"
                        ]
                        # 1) nodes, using HTML-style labels so we can do two lines
                        for pg in flat_df["Parent Group"].unique():
                            chosen = rename_map.get(pg)
                            if chosen:
                                # group name on the first line, chosen item in smaller font below
                                label_html = f'<<B>{pg}</B><BR/><FONT POINT-SIZE="10">{chosen}</FONT>>'
                            else:
                                label_html = f'"{pg}"'
                            dot.append(
                            f'  "{pg}" [label={label_html}, '
                            f'shape=box, style=filled, fillcolor=lightblue];'
                            )

                        for dg in flat_df["Dependent Group"].unique():
                            chosen = rename_map.get(dg)
                            if chosen:
                                label_html = f'<<B>{dg}</B><BR/><FONT POINT-SIZE="10">{chosen}</FONT>>'
                            else:
                                label_html = f'"{dg}"'
                            dot.append(
                            f'  "{dg}" [label={label_html}, '
                            f'shape=ellipse, style=filled, fillcolor=lightgreen];'
                            )

                        # 2) edges, translating the Type into your friendly verbs
                        for _, r in flat_df.iterrows():
                            orig = r["Type"]
                            verb = type_label_map.get(orig, orig)
                            style = "solid" if orig == "Objective" else "dashed"
                            color = "blue"   if orig == "Objective" else "gray"
                            dot.append(
                            f'  "{r["Parent Group"]}" -> "{r["Dependent Group"]}" '
                            f'[label="{verb} ({r["Multiple"]})", style="{style}", color="{color}"];'
                            )

                        dot.append("}")
                        st.graphviz_chart("\n".join(dot), use_container_width=True)

                    # 7) Total bundle price – only once a parent is selected and its required Objective mappings are chosen
                    # 7a) which parents did the user pick?
                    selected_parents = [pg for pg, sel in sel_parent.items() if sel]

                    # 7b) if none picked, prompt and don't calculate
                    if not selected_parents:
                        st.info("Please select at least one parent product to begin bundle pricing.")
                    else:
                        # 7c) for each selected parent gather its required (Objective) dependents
                        missing = []
                        for pg in selected_parents:
                            required_dgs = flat_df[
                                (flat_df["Parent Group"] == pg) & (flat_df["Type"] == "Objective")
                            ]["Dependent Group"].unique().tolist()
                            for dg in required_dgs:
                                if not sel_dependent.get(dg):
                                    missing.append(f"{dg} (for {pg})")

                        # 7d) if any required dependent is still un-selected, prompt and stop
                        if missing:
                            st.info(
                                "Please select all required Objective mappings before "
                                "we can calculate your total bundle price.  "
                                f"Missing: {', '.join(missing)}"
                            )
                        else:
                            # 7e) now compute total: sum picked parents + any picked dependents (Objective or Subjective)
                            total = 0.0
                            for pg in selected_parents:
                                row = parent_dfs[pg][parent_dfs[pg]["Name"] == sel_parent[pg]]
                                if not row.empty:
                                    total += float(row["_price"].iloc[0] or 0)
                            for dg, dfd in dependent_dfs.items():
                                sel = sel_dependent.get(dg)
                                if sel:
                                    row = dfd[dfd["Name"] == sel]
                                    if not row.empty:
                                        total += float(row["_price"].iloc[0] or 0)

                            st.markdown(f"**Total Bundle Price:** ${total:.2f}")

                            # 8) Bill of Materials
                            bom = [
                                (g, s)
                                for g, s in list(sel_parent.items()) + list(sel_dependent.items())
                                if s
                            ]
                            if bom:
                                st.markdown("**Bill of Materials**")
                                for group, prod in bom:
                                    st.write(f"- {group}: {prod}")
                else:
                    st.info("No bundle configuration found or failed to load.")
                # ----- Section 4: Videos -----
                st.markdown("---")
                st.header("Videos")
                video_indices = []
                for col in series_info.index:
                    m = re.match(r"Video (\d+)$", col)
                    if m:
                        video_indices.append(int(m.group(1)))
                video_indices.sort()
                valid_video_indices = []
                for idx in video_indices:
                    url_field = f"Video {idx}"
                    name_field = f"Video {idx} name"
                    video_url = series_info.get(url_field, "")
                    video_name = series_info.get(name_field, "")
                    if (pd.notna(video_url) and str(video_url).strip()) or (pd.notna(video_name) and str(video_name).strip()):
                        valid_video_indices.append(idx)
                if valid_video_indices:
                    for i in range(0, len(valid_video_indices), 2):
                        chunk = valid_video_indices[i:i+2]
                        cols = st.columns(len(chunk))
                        for col_idx, idx in enumerate(chunk):
                            with cols[col_idx]:
                                name_field = f"Video {idx} name"
                                url_field = f"Video {idx}"
                                video_name = series_info.get(name_field, "")
                                video_url = series_info.get(url_field, "")
                                video_name = video_name if pd.notna(video_name) else ""
                                video_url = video_url if pd.notna(video_url) else ""
                                video_url = str(video_url).strip()
                                if video_name:
                                    st.subheader(video_name)
                                thumbnail_url = get_youtube_thumbnail(video_url) if video_url else None
                                if thumbnail_url:
                                    st.image(thumbnail_url, width=200)
                                else:
                                    st.write("No thumbnail available")
                                with st.expander("Watch Video"):
                                    if video_url:
                                        st.video(video_url)
                                    else:
                                        st.info("No URL provided")
                    st.markdown("---")
                else:
                    st.info("No videos available")

                # ----- Section 5: Internal Document -----
                st.markdown("---")
                st.header("Internal Document")
                doc_link = series_info.get("Internal document 1", "")
                doc_desc = series_info.get("Internal document 1 description", "")
                if doc_link and doc_link.strip():
                    if doc_desc and doc_desc.strip():
                        st.write(doc_desc)
                    if st.button("Show Document", key="internal_doc_btn"):
                        st.markdown(f'<a href="{doc_link}" target="_blank"><button class="buy-button">Show Internal Document</button></a>', unsafe_allow_html=True)
                else:
                    st.info("No internal document available")

                # ----- Section 6: Downloads -----
                st.markdown("---")
                st.header("Downloads")
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
      <p><strong>List Price:</strong> <span class="price">${row['List Price']}</span></p>
      <p><strong>Distributor Price:</strong> <span class="price">${row['Distributor Price']}</span></p>
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
                    if "List Price" in table_df.columns:
                        table_df["List Price"] = table_df["List Price"].apply(format_price)
                    if "Distributor Price" in table_df.columns:
                        table_df["Distributor Price"] = table_df["Distributor Price"].apply(format_price)
                    cols_to_show = ["Name", "Description", "List Price", "Distributor Price", "Promo Catalogue Print?", "Buy URL"]
                    cols_to_show = [col for col in cols_to_show if col in table_df.columns]
                    display_df = table_df.reset_index(drop=True)
                    st.table(display_df.head(10)[cols_to_show])
                    if len(display_df) > 10:
                        with st.expander("Show more"):
                            st.table(display_df.iloc[10:][cols_to_show])

# ------------------------- Hide Streamlit Menu -------------------------
# hide_st_style = """
#             <style>
#             #MainMenu {visibility: hidden;}
#             footer {visibility: hidden;}
#             header {visibility: hidden;}
#             </style>
# """
# st.markdown(hide_st_style, unsafe_allow_html=True)
