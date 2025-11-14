import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pyproj import Transformer
import pydeck as pdk
import json

st.set_page_config(page_title="Geo Tools Suite", layout="centered")

# =========================================================
#                   LANDING PAGE MENU
# =========================================================

st.title("🌍 Geo Tools Suite")

tool = st.sidebar.selectbox(
    "Select a Tool",
    ["🏠 Home", "Nigeria LGA Finder", "Parcel Plotter"]
)

if tool == "🏠 Home":
    st.header("Welcome!")
    st.write("""
    Select any of the tools from the sidebar:
    
    ### 🗺️ Nigeria LGA Finder  
    Enter Easting/Northing and find which LGA the point belongs to.
    
    ### 📐 Parcel Plotter  
    Input coordinates, plot a parcel boundary and calculate the area.
    """)


# =========================================================
#                   NIGERIA LGA FINDER
# =========================================================
elif tool == "Nigeria LGA Finder":

    st.header("🗺️ Nigeria LGA Finder (Offline)")

    @st.cache_resource
    def load_lga_data():
        return gpd.read_file("NGA_LGA_Boundaries_2_-2954311847614747693.geojson")

    lga_gdf = load_lga_data()

    E = st.number_input("Easting (m)", format="%.2f")
    N = st.number_input("Northing (m)", format="%.2f")

    projected_crs = "EPSG:32632"
    transformer = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)

    if st.button("Find LGA"):

        lon, lat = transformer.transform(E, N)
        point = Point(lon, lat)

        match = lga_gdf[lga_gdf.contains(point)]

        if not match.empty:
            name_cols = [c for c in match.columns if "NAME" in c.upper()]
            lga_name = match.iloc[0][name_cols[0]] if name_cols else "Unknown"

            st.success(f"✅ This coordinate is inside **{lga_name} LGA**")

            # --- Polygon Data ---
            geojson_dict = json.loads(match.to_json())
            polygon_data = []

            for feat in geojson_dict["features"]:
                t = feat["geometry"]["type"]
                coords = feat["geometry"]["coordinates"]

                if t == "Polygon":
                    polygon_data.append({"coordinates": coords})
                elif t == "MultiPolygon":
                    for poly in coords:
                        polygon_data.append({"coordinates": poly})

            polygon_layer = pdk.Layer(
                "PolygonLayer",
                polygon_data,
                get_polygon="coordinates",
                get_fill_color="[0, 120, 255, 60]",
                get_line_color="[0, 80, 200]",
                stroked=True,
            )

            # INTERACTIVE ZOOM-SCALING POINT MARKER
            point_layer = pdk.Layer(
                "ScatterplotLayer",
                [{"lon": lon, "lat": lat}],
                get_position="[lon, lat]",
                get_color="[255, 0, 0]",
                radius_scale=1,
                radius_min_pixels=5,
                radius_max_pixels=40,
            )

            centroid = Point(lon, lat)

            st.pydeck_chart(
                pdk.Deck(
                    layers=[polygon_layer, point_layer],
                    initial_view_state=pdk.ViewState(
                        latitude=centroid.y,
                        longitude=centroid.x,
                        zoom=10
                    ),
                    map_style=None
                )
            )
        else:
            st.error("❌ No LGA found for this location.")



# =========================================================
#                      PARCEL PLOTTER
# =========================================================
elif tool == "Parcel Plotter":

    st.header("📐 Parcel Boundary Plotter (UTM Coordinates)")
    st.write("Enter UTM Easting/Northing (Zone 32N, meters).")

    # CRS definitions
    projected_crs = "EPSG:32632"    # UTM Zone 32N
    transformer = Transformer.from_crs(projected_crs, "EPSG:4326", always_xy=True)

    num_points = st.number_input("Number of beacons:", min_value=3, step=1)

    utm_coords = []
    if num_points > 0:
        for i in range(num_points):
            col1, col2 = st.columns(2)
            e = col1.number_input(f"Point {i+1} → Easting (m)", key=f"e{i}", format="%.2f")
            n = col2.number_input(f"Point {i+1} → Northing (m)", key=f"n{i}", format="%.2f")
            utm_coords.append((e, n))

    if st.button("Plot Parcel"):

        try:
            # Auto-close polygon
            if utm_coords[0] != utm_coords[-1]:
                utm_coords.append(utm_coords[0])

            # Build polygon in UTM for accurate area
            polygon = Polygon(utm_coords)

            if not polygon.is_valid:
                st.error("❌ Invalid boundary shape. Check point sequence.")
            else:

                # AREA IN SQUARE METERS (correct, because UTM)
                area = polygon.area
                st.success("✅ Parcel plotted successfully!")
                st.write(f"### Area: **{area:,.2f} m²**")

                # Convert UTM → Lat/Lon for mapping
                ll_coords = [transformer.transform(x, y) for x, y in utm_coords]

                # Polygon for pydeck
                polygon_data = [{
                    "coordinates": [ll_coords]
                }]

                polygon_layer = pdk.Layer(
                    "PolygonLayer",
                    polygon_data,
                    get_polygon="coordinates",
                    get_fill_color="[0, 150, 255, 80]",
                    get_line_color="[0, 50, 200]",
                    stroked=True,
                )

                point_layer = pdk.Layer(
                    "ScatterplotLayer",
                    [{"lon": lon, "lat": lat} for lon, lat in ll_coords],
                    get_position="[lon, lat]",
                    get_color="[255, 0, 0]",
                    radius_scale=1,
                    radius_min_pixels=3,
                    radius_max_pixels=30,
                )

                # Center on the polygon centroid
                centroid_lon, centroid_lat = transformer.transform(
                    polygon.centroid.x,
                    polygon.centroid.y
                )

                # 🟦 SAME BASEMAP AS LGA FINDER (map_style=None)
                st.pydeck_chart(
                    pdk.Deck(
                        layers=[polygon_layer, point_layer],
                        initial_view_state=pdk.ViewState(
                            longitude=centroid_lon,
                            latitude=centroid_lat,
                            zoom=17
                        ),
                        map_style=None  # <-- SAME BASEMAP
                    )
                )

        except Exception as e:
            st.error(f"Error: {e}")
