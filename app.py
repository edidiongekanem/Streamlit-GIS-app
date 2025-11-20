import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pyproj import Transformer
import pydeck as pdk
import json
from math import log2
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

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

    projected_crs = "EPSG:32632"
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
            if utm_coords[0] != utm_coords[-1]:
                utm_coords.append(utm_coords[0])

            polygon = Polygon(utm_coords)

            if not polygon.is_valid:
                st.error("❌ Invalid boundary shape. Check point sequence.")
            else:
                area = polygon.area
                st.success("✅ Parcel plotted successfully!")
                st.write(f"### Area: **{area:,.2f} m²**")

                # Convert UTM → Lat/Lon
                ll_coords = [transformer.transform(x, y) for x, y in utm_coords]

                # --- Calculate min/max and parcel dimensions BEFORE using them ---
                lons, lats = zip(*ll_coords)
                min_lon, max_lon = min(lons), max(lons)
                min_lat, max_lat = min(lats), max(lats)
                parcel_width = max_lon - min_lon
                parcel_height = max_lat - min_lat

                # --- Map rendering ---
                polygon_data = [{"coordinates": [ll_coords]}]

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

                # Auto-zoom
                lon_center = sum(lons)/len(lons)
                lat_center = sum(lats)/len(lats)
                lon_range = max(lons) - min(lons)
                lat_range = max(lats) - min(lats)
                max_range = max(lon_range, lat_range)
                zoom_level = 8 if max_range == 0 else min(17, 8 - log2(max_range/360))

                tile_layer = pdk.Layer(
                    "TileLayer",
                    "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
                    min_zoom=0,
                    max_zoom=19,
                    tile_size=256,
                    render_sub_layers=True,
                    pickable=False,
                )

                st.pydeck_chart(
                    pdk.Deck(
                        layers=[tile_layer, polygon_layer, point_layer],
                        initial_view_state=pdk.ViewState(
                            longitude=lon_center,
                            latitude=lat_center,
                            zoom=zoom_level,
                            pitch=0,
                        )
                    )
                )

                # --- PDF Sketch ---
                buffer = BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                width, height = A4

                # Title block (centered with dotted lines)
                c.setFont("Helvetica-Bold", 12)
                title_y = height - 50
                line_spacing = 24
                lines = [
                    "PLAN SHEWING LANDED PROPERTY",
                    "OF",
                    "." * 50,
                    "AT",
                    "." * 40,
                    "." * 40,
                    "." * 40,
                    "." * 40
                ]
                for i, line in enumerate(lines):
                    y = title_y - i * line_spacing
                    if line.startswith("."):
                        c.setLineWidth(1)
                        c.setDash(1, 2)
                        c.line(width/2 - 250, y, width/2 + 250, y)
                        c.setDash()
                    else:
                        c.drawCentredString(width / 2, y, line)

                # --- Calculate scale ratio and draw survey scale bar ---
                top_margin = 150  # buffer for title block etc.
                page_center_y = (height - top_margin)/2 - 30

                printable_width_pt = width - 100
                printable_width_m = parcel_width
                scale_ratio = printable_width_m / (printable_width_pt * 0.0254 / 72)
                scale_ratio = int(round(scale_ratio / 500.0) * 500)

                scale_bar_length_pt = 100
                scale_bar_m = scale_bar_length_pt * scale_ratio * 0.0254 / 72  # meters
                scale_bar_y = title_y - len(lines)*line_spacing - 10
                c.setStrokeColor(colors.black)
                c.line(width/2 - scale_bar_length_pt/2, scale_bar_y, width/2 + scale_bar_length_pt/2, scale_bar_y)
                c.drawCentredString(width/2, scale_bar_y - 12, f"1:{scale_ratio}  ({scale_bar_m:.0f} m)")

                # Origin & Area below scale bar
                c.setFont("Helvetica", 10)
                c.drawCentredString(width/2, scale_bar_y - 30, "ORIGIN: UTM ZONE 32N")
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(colors.red)
                c.drawCentredString(width/2, scale_bar_y - 45, f"AREA = {area:,.2f} m²")
                c.setFillColor(colors.black)

                # Scale & center polygon on page
                scale_factor = 0.6
                scale_x = (width - 100) / parcel_width if parcel_width != 0 else 1
                scale_y = (height - top_margin - 100) / parcel_height if parcel_height != 0 else 1
                scale = scale_factor * min(scale_x, scale_y)
                center_x = (min_lon + max_lon)/2
                center_y = (min_lat + max_lat)/2
                page_center_x = width/2

                def transform_point(lon, lat):
                    x = (lon - center_x) * scale + page_center_x
                    y = (lat - center_y) * scale + page_center_y
                    return x, y

                scaled_points = [transform_point(lon, lat) for lon, lat in ll_coords]

                # Draw black polygon
                c.setLineWidth(2)
                c.setStrokeColor(colors.black)
                x_points = [x for x, y in scaled_points]
                y_points = [y for x, y in scaled_points]
                c.lines(list(zip(x_points, y_points, x_points[1:] + [x_points[0]], y_points[1:] + [y_points[0]])))

                # Red points and labels
                c.setFillColor(colors.red)
                c.setFont("Helvetica", 10)
                for idx, (x, y) in enumerate(scaled_points, start=1):
                    c.circle(x, y, 3, fill=1)
                    c.setFillColor(colors.black)
                    c.drawString(x + 5, y + 2, f"P{idx}")
                    c.setFillColor(colors.red)

                # True North above Point 1
                x1, y1 = scaled_points[0]
                north_len = 70
                c.setStrokeColor(colors.black)
                c.setLineWidth(1.5)
                c.line(x1, y1, x1, y1 + north_len)
                c.line(x1, y1 + north_len, x1 - 5, y1 + north_len - 10)
                c.line(x1, y1 + north_len, x1 + 5, y1 + north_len - 10)
                c.setFont("Helvetica-Bold", 10)
                c.drawCentredString(x1, y1 + north_len + 10, "N")

                c.showPage()
                c.save()
                buffer.seek(0)

                st.download_button(
                    label="💾 Download Parcel PDF",
                    data=buffer,
                    file_name="parcel_sketch.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Error: {e}")
