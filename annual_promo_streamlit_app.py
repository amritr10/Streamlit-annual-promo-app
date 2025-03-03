#!/usr/bin/env python
import streamlit as st
import pandas as pd
import re

# ------------------------- Page Setup -------------------------
st.set_page_config(page_title="Annual Promotion Sale", layout="wide")

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
    }
    .subsection-header h3 {
        margin: 0;
        color: #495057;
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
    </style>
    """, unsafe_allow_html=True)

# ------------------------- Promotion Header -------------------------
st.markdown('<div class="promo-header"><h1>Annual Promotion Sale</h1></div>', unsafe_allow_html=True)

# ------------------------- Load Data -------------------------
# Adjust the CSV file path as needed.
csv_file = r"C:\Users\amrit.ramadugu\Downloads\Streamlit annual promo app\model-export 20-02-25.csv"
df = pd.read_csv(csv_file)

# Drop rows missing Category or Series.
df = df.dropna(subset=["Category", "Series"])

# ------------------------- Sidebar Filters -------------------------
# Category filter – include an "All Categories" option.
all_categories = sorted(df["Category"].dropna().unique())
selected_category = st.sidebar.selectbox("Select Category", options=["All Categories"] + all_categories)

if selected_category != "All Categories":
    filtered_df = df[df["Category"] == selected_category].copy()
else:
    filtered_df = df.copy()

# Series filter – based on (possibly) category–filtered data.
available_series = sorted(filtered_df["Series"].dropna().unique())
selected_series = st.sidebar.multiselect("Select Series", options=available_series, default=[],
                                           help="Select one or more series to filter products")
if selected_series:
    filtered_df = filtered_df[filtered_df["Series"].isin(selected_series)]

# ------------------------- Specification Filters -------------------------
# Always initialize spec_filters so it exists.
spec_filters = {}

if selected_series:
    st.sidebar.subheader("Specification Filters")
    # Assumption: spec columns have a header like "SpecName;SpecType"
    spec_columns = [col for col in filtered_df.columns if ";" in col]
    
    for spec_col in spec_columns:
        # Only process a spec if there is at least one non-null value.
        if not filtered_df[spec_col].notna().any():
            continue
        
        # Split header into spec_name and spec_type.
        parts = spec_col.split(";", 1)
        spec_name = parts[0].strip()
        spec_type = parts[1].strip().lower()
        
        if spec_type == "lov":
            # For list-of-values filters, build a unique set of choices.
            values_set = set()
            for cell in filtered_df[spec_col].dropna():
                for v in str(cell).split(";"):
                    clean_val = v.strip()
                    if clean_val:
                        values_set.add(clean_val)
            options_list = sorted(values_set)
            if options_list:
                selected_options = st.sidebar.multiselect(f"{spec_name} (LOV)", options=options_list, default=[])
                if selected_options:
                    spec_filters[spec_col] = ("lov", selected_options)
                    
        elif spec_type == "number":
            # For the "number" spec, we expect a string like "x {SI notation}" or simply "x".
            # Use a regex to capture the numeric part and optional SI unit.
            pattern_number = re.compile(r'^\s*(-?\d+(?:\.\d+)?)(.*)$')
            number_list = []
            si_unit = ""
            for cell in filtered_df[spec_col].dropna():
                m = pattern_number.match(str(cell))
                if m:
                    try:
                        value = float(m.group(1))
                        number_list.append(value)
                        # Optionally capture SI notation if available.
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
                apply_filter = st.sidebar.checkbox(f"Filter by {label}")
                if apply_filter:
                    # Create a double slider (range slider) returning a tuple (sel_min, sel_max).
                    selected_range = st.sidebar.slider(f"{spec_name} (number)", 
                                                         min_value=global_min,
                                                         max_value=global_max,
                                                         value=(global_min, global_max))
                    spec_filters[spec_col] = ("number", selected_range)
                    
        elif spec_type == "logical":
            logical_choice = st.sidebar.radio(f"{spec_name} (logical)", options=["Any", "True", "False"], index=0)
            if logical_choice != "Any":
                spec_filters[spec_col] = ("logical", logical_choice)
                
        elif spec_type == "range":
            # For a "range" spec, expected cell formats:
            # "x-y {SI notation}" or "-x-y {SI notation}" or simply "x-y"
            range_pattern = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)(.*)$')
            range_list = []
            for cell in filtered_df[spec_col].dropna():
                m = range_pattern.match(str(cell))
                if m:
                    try:
                        low = float(m.group(1))
                        high = float(m.group(2))
                        # Ensure low is not greater than high.
                        if low > high:
                            low, high = high, low
                        range_list.append((low, high))
                    except Exception:
                        continue
            if range_list:
                global_min = min(t[0] for t in range_list)
                global_max = max(t[1] for t in range_list)
                si_unit = ""
                for cell in filtered_df[spec_col].dropna():
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
                apply_range = st.sidebar.checkbox(f"Filter by {label}")
                if apply_range:
                    # Create a double slider for the range filter.
                    selected_vals = st.sidebar.slider(f"{spec_name} (range)",
                                                        min_value=global_min,
                                                        max_value=global_max,
                                                        value=(global_min, global_max))
                    spec_filters[spec_col] = ("range", selected_vals)
else:
    st.sidebar.info("Select at least one series to filter specifications further.")

# ------------------------- Apply Specification Filters -------------------------
for col, (filter_type, filter_value) in spec_filters.items():
    if filter_type == "lov":
        # For LOV, include the product if any selected option appears in the cell's value.
        filtered_df = filtered_df[ filtered_df[col].apply(
            lambda cell: bool(set(v.strip() for v in str(cell).split(";") if v.strip()) & set(filter_value)) if pd.notna(cell) else False )
        ]
    elif filter_type == "number":
        # For "number", use the same regex to extract the numeric value and check if it falls within the range.
        pattern_number = re.compile(r'^\s*(-?\d+(?:\.\d+)?)(.*)$')
        def match_number(cell):
            if pd.isna(cell):
                return False
            try:
                m = pattern_number.match(str(cell))
                if m:
                    num_val = float(m.group(1))
                    return filter_value[0] <= num_val <= filter_value[1]
                return False
            except Exception:
                return False
        filtered_df = filtered_df[ filtered_df[col].apply(match_number) ]
    elif filter_type == "logical":
        def match_logical(cell):
            if pd.isna(cell):
                return False
            return str(cell).strip().lower() == filter_value.lower()
        filtered_df = filtered_df[ filtered_df[col].apply(match_logical) ]
    elif filter_type == "range":
        # For "range", use the regex to extract the low and high numbers from each cell.
        range_pattern = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*-\s*(-?\d+(?:\.\d+)?)(.*)$')
        def match_range(cell):
            if pd.isna(cell):
                return False
            try:
                m = range_pattern.match(str(cell))
                if m:
                    low = float(m.group(1))
                    high = float(m.group(2))
                    # Product qualifies if its range overlaps with the slider-selected range.
                    # That is, if the product's high is at least the selected lower bound and
                    # its low is at most the selected upper bound.
                    return (high >= filter_value[0]) and (low <= filter_value[1])
                return False
            except Exception:
                return False
        filtered_df = filtered_df[ filtered_df[col].apply(match_range) ]

# ------------------------- Main Content: Group and Display Products -------------------------
if filtered_df.empty:
    st.info("No products found with the current filters.")
else:
    # Group products by Category and then by Series.
    for category, cat_data in filtered_df.groupby("Category", sort=False):
        st.markdown(f'<div class="section-header"><h2>Category: {category}</h2></div>', unsafe_allow_html=True)
        for series, series_data in cat_data.groupby("Series", sort=False):
            st.markdown(f'<div class="subsection-header"><h3>Series: {series}</h3></div>', unsafe_allow_html=True)
            for idx, row in series_data.iterrows():
                with st.expander(row["Name"]):
                    col1, col2 = st.columns([1, 2])
                    if pd.notna(row["Featured image"]):
                        try:
                            col1.image(row["Featured image"], width=100)
                        except Exception:
                            col1.markdown("Image not available")
                    else:
                        col1.markdown("No image available")
                    
                    details = f"""
**Description:** {row["Description"]}

**Price:** ${row["Sale price in Australia"]}

**SKU:** {row["SKU"]}
                    """
                    col2.markdown(details)
                    
                    buy_url = f"https://store.omron.com.au/product/{row['SKU']}"
                    st.markdown(f'<a href="{buy_url}" target="_blank"><button class="buy-button">Buy Now</button></a>',
                                unsafe_allow_html=True)