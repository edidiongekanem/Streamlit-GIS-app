import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pyproj import Transformer
import pydeck as pdk
import json
import math

st.set_page_config(page_title="Geo Tools Suite", layout="centered")

# =========================================================
#                   LANDING PAGE MENU
# =========================================================

st.title("🌍 Geo Tools Suite")

tool = st.sidebar.selectbox(
    "Select a Tool",
    ["🏠 Home", "Nigeria LGA Finder", "Parcel Plotter"]
)

# =========================================================
#                          HOME
# =========================================================
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
        gdf = gpd.read_file("NGA_LGA_Boundaries_2_-2954311847614747693.geojson")
        return gdf.to_crs("EPSG:4326")  # ensure WGS84

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

            st.pydeck_chart(
                pdk.Deck(
                    layers=[polygon_layer, point_layer],
                    initial_view_state=pdk.ViewState(
                        latitude=lat,
                        longitude=lon,
                        zoom=10
                    )
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

                ll_coords = [transformer.transform(x, y) for x, y in utm_coords]

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

                # --- Auto-zoom ---
                lons, lats = zip(*ll_coords)
                lon_center = sum(lons)/len(lons)
                lat_center = sum(lats)/len(lats)
                lon_range = max(lons) - min(lons)
                lat_range = max(lats) - min(lats)
                max_range = max(lon_range, lat_range)
                import math
                zoom_level = 8 if max_range == 0 else min(17, 8 - math.log2(max_range/360))

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

                # --- PDF Sketch Download (Template Version) ---
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import A4
                from reportlab.lib import colors
                from io import BytesIO

                buffer = BytesIO()
                c = canvas.Canvas(buffer, pagesize=A4)
                width, height = A4

                # --- Title Block ---
                c.setFont("Helvetica-Bold", 12)
                c.drawCentredString(width/2, height - 50, "PLAN SHEWING LANDED PROPERTY")
                c.setFont("Helvetica", 12)
                c.drawCentredString(width/2, height - 70, "OF")
                c.line(width/2 - 100, height - 75, width/2 + 100, height - 75)  # dotted line
                c.drawCentredString(width/2, height - 95, "AT")
                c.line(width/2 - 100, height - 100, width/2 + 100, height - 100)  # dotted line

                y_line = height - 120
                for _ in range(3):
                    c.line(width/2 - 100, y_line, width/2 + 100, y_line)
                    y_line -= 20

                # --- Scale & Center Polygon ---
                min_lon, max_lon = min(lons), max(lons)
                min_lat, max_lat = min(lats), max(lats)
                parcel_width = max_lon - min_lon
                parcel_height = max_lat - min_lat
                scale_factor = 0.6  # 60% of page

                page_width, page_height = width - 100, height - 200
                scale_x = page_width / parcel_width if parcel_width != 0 else 1
                scale_y = page_height / parcel_height if parcel_height != 0 else 1
                scale = scale_factor * min(scale_x, scale_y)

                center_x = (min_lon + max_lon)/2
                center_y = (min_lat + max_lat)/2
                page_center_x = width/2
                page_center_y = height/2 - 30

                def transform_point(lon, lat):
                    x = (lon - center_x) * scale + page_center_x
                    y = (lat - center_y) * scale + page_center_y
                    return x, y

                scaled_points = [transform_point(lon, lat) for lon, lat in ll_coords]

                # --- Draw black polygon ---
                c.setLineWidth(2)
                c.setStrokeColor(colors.black)
                x_points = [x for x, y in scaled_points]
                y_points = [y for x, y in scaled_points]
                c.lines(list(zip(x_points, y_points, x_points[1:] + [x_points[0]], y_points[1:] + [y_points[0]])))

                # --- Draw red points and labels ---
                c.setFillColor(colors.red)
                c.setFont("Helvetica", 10)
                for idx, (x, y) in enumerate(scaled_points, start=1):
                    c.circle(x, y, 3, fill=1)
                    c.setFillColor(colors.black)
                    c.drawString(x + 5, y + 2, f"P{idx}")
                    c.setFillColor(colors.red)

                # --- True North Symbol ---
                x1, y1 = scaled_points[0]
                north_len = 50
                c.setStrokeColor(colors.black)
                c.setLineWidth(1.5)
                c.line(x1, y1, x1, y1 + north_len)
                c.line(x1, y1 + north_len, x1 - 5, y1 + north_len - 10)
                c.line(x1, y1 + north_len, x1 + 5, y1 + north_len - 10)
                c.setFont("Helvetica-Bold", 10)
                c.drawCentredString(x1, y1 + north_len + 10, "N")

                # --- Scale bar placeholder ---
                scale_bar_width = 100
                c.setStrokeColor(colors.black)
                c.line(width/2 - scale_bar_width/2, 50, width/2 + scale_bar_width/2, 50)
                c.drawCentredString(width/2, 35, "SCALE: 1:X (INSERT)")

                # --- Parcel description block (top-right) ---
                block_width = 200
                block_height = 100
                margin = 40
                x0 = width - block_width - margin
                y0 = height - margin
                c.setLineWidth(1.5)
                c.setStrokeColorRGB(0, 0, 0)
                c.rect(x0, y0 - block_height, block_width, block_height, stroke=1, fill=0)

                # Add placeholder text lines
                c.setFont("Helvetica", 9)
                text_y = y0 - 15
                lines = ["Parcel Description:", "Owner Name: ____________", "Location: ____________", "Survey No: ____________", "Area: ____________"]
                for line in lines:
                    c.drawString(x0 + 5, text_y, line)
                    text_y -= 15

                # --- Origin & Area ---
                c.setFont("Helvetica", 10)
                c.drawString(50, 20, "ORIGIN: UTM ZONE 32N")
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(colors.red)
                c.drawString(250, 20, f"AREA = {area:,.2f} m²")
                c.setFillColor(colors.black)

                c.showPage()
                c.save()
                buffer.seek(0)

                st.download_button(
                    label="💾 Download Parcel PDF",
                    data=buffer,
                    file_name="parcel_sketch_template.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Error: {e}")

