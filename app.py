import streamlit as st
import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer
import pydeck as pdk

st.set_page_config(page_title="Offline Nigeria LGA Finder", layout="centered")

# ------------------------
# Load GeoJSON (EPSG:4326)
# ------------------------
@st.cache_resource
def load_lga_data():
    gdf = gpd.read_file("NGA_LGA_Boundaries_2_-2954311847614747693.geojson")
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
projected_crs = "EPSG:32632"  # example CRS
transformer = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)

if st.button("Find LGA"):
    # Convert meters to lat/lon
    lon, lat = transformer.transform(E, N)
    point = Point(lon, lat)
    
    # Check which LGA contains the point
    match = lga_gdf[lga_gdf.contains(point)]
    
    if not match.empty:
        # Try to find a column with 'NAME'
        name_cols = [c for c in match.columns if "NAME" in c.upper()]
        if name_cols:
            lga_name = match.iloc[0][name_cols[0]]
        else:
            lga_name = "Unknown"
        
        st.success(f"✅ The coordinate is in **{lga_name} LGA**.")

        # -------------------------------------------------
        # 🔥 NEW POLYGON MAP SECTION (PASTE HERE)
        # -------------------------------------------------
        poly_json = match.__geo_interface__["features"][0]["geometry"]

        polygon_layer = pdk.Layer(
            "PolygonLayer",
            [poly_json],
            get_polygon="coordinates",
            get_fill_color="[0, 100, 255, 60]",
            get_line_color="[0, 50, 200]",
            pickable=False,
            extruded=False,
            stroked=True,
        )

        point_layer = pdk.Layer(
            "ScatterplotLayer",
            [{"lon": lon, "lat": lat}],
            get_position="[lon, lat]",
            get_color="[255, 0, 0]",
            get_radius=200,
        )

        view_state = pdk.ViewState(
            longitude=lon,
            latitude=lat,
            zoom=9,
            pitch=0,
        )

        st.subheader("📍 LGA Boundary Map")
        st.pydeck_chart(pdk.Deck(layers=[polygon_layer, point_layer],
                                 initial_view_state=view_state))
        # -------------------------------------------------
        
    else:
        st.error("❌ No LGA found for this coordinate.")
