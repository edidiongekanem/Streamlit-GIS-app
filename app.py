import streamlit as st
import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer

st.set_page_config(page_title="Offline Nigeria LGA Finder", layout="centered")

# ------------------------
# Load GeoJSON (EPSG:4326)
# ------------------------
@st.cache_resource
def load_lga_data():
    gdf = gpd.read_file("NGA_LGA_Boundaries_2_-2954311847614747693.geojson")  # your GeoJSON in lat/lon
    return gdf

lga_gdf = load_lga_data()

st.title("🗺️ Nigeria LGA Finder (Offline)")
st.write("Enter **Easting/Northing (meters)** in your projected CRS to find the LGA.")

# ------------------------
# User input in meters
# ------------------------
E = st.number_input("Easting (m)", format="%.2f")
N = st.number_input("Northing (m)", format="%.2f")

# ------------------------
# CRS Transformation
# ------------------------
# Replace 32632 with your projected CRS if different
projected_crs = "EPSG:32632"  # example: UTM Zone 32N
transformer = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)

if st.button("Find LGA"):
    # Convert meters to lat/lon
    lon, lat = transformer.transform(E, N)
    point = Point(lon, lat)
    
    # Check which LGA contains the point
    match = lga_gdf[lga_gdf.contains(point)]
    
    if not match.empty:
        # Try to find a column with 'NAME' in it
        name_cols = [c for c in match.columns if "NAME" in c.upper()]
        if name_cols:
            lga_name = match.iloc[0][name_cols[0]]
        else:
            lga_name = "Unknown"
        st.success(f"✅ The coordinate is in **{lga_name} LGA**.")
    else:
        st.error("❌ No LGA found for this coordinate.")
