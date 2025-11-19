import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pyproj import Transformer
import pydeck as pdk
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

st.set_page_config(page_title="Geo Tools Suite", layout="centered")

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

                centroid_lon, centroid_lat = transformer.transform(
                    polygon.centroid.x,
                    polygon.centroid.y
                )

                st.pydeck_chart(
                    pdk.Deck(
                        layers=[polygon_layer, point_layer],
                        initial_view_state=pdk.ViewState(
                            longitude=centroid_lon,
                            latitude=centroid_lat,
                            zoom=17
                        ),
                        map_style=None
                    )
                )

                # ----------- PRINT OPTIONS -----------
                colA, colB = st.columns(2)

                # =======================
                # 1️⃣ SKETCH PLAN PDF
                # =======================
                if colA.button("📄 Print Sketch Plan"):
                    try:
                        pdf_file = "parcel_sketch_plan.pdf"
                        styles = getSampleStyleSheet()
                        doc = SimpleDocTemplate(pdf_file, pagesize=A4)
                        story = []

                        story.append(Paragraph("<b>Parcel Sketch Plan</b>", styles['Title']))
                        story.append(Spacer(1, 12))
                        story.append(Paragraph(f"<b>Area:</b> {area:,.2f} m²", styles['Normal']))
                        story.append(Spacer(1, 12))

                        # Coordinate Table
                        from reportlab.platypus import Table, TableStyle
                        from reportlab.lib import colors
                        table_data = [["Point", "Easting", "Northing"]]
                        for idx, (xe, yn) in enumerate(utm_coords):
                            table_data.append([f"{idx+1}", f"{xe:.2f}", f"{yn:.2f}"])
                        coord_table = Table(table_data, colWidths=[60, 120, 120])
                        coord_table.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                            ('GRID', (0,0), (-1,-1), 1, colors.black)
                        ]))
                        story.append(coord_table)
                        story.append(Spacer(1, 20))

                        doc.build(story)
                        with open(pdf_file, "rb") as f:
                            st.download_button("⬇️ Download Sketch Plan", f, pdf_file, mime="application/pdf")
                    except Exception as e:
                    st.error(f"Error: {e}")(f"PDF error: {e}")

                # ================================
                # 2️⃣ COMPUTATION SHEET PDF
                # ================================
                if colB.button("📊 Print Computation Sheet"):
                    try:
                        pdf_file = "parcel_computation_sheet.pdf"
                        styles = getSampleStyleSheet()
                        doc = SimpleDocTemplate(pdf_file, pagesize=A4)
                        story = []

                        story.append(Paragraph("<b>Parcel Computation Sheet</b>", styles['Title']))
                        story.append(Spacer(1, 10))
                        story.append(Paragraph(f"<b>Total Area:</b> {area:,.2f} m²", styles['Heading2']))
                        story.append(Spacer(1, 15))

                        # COMPUTATIONS: DISTANCES, BEARINGS, ANGLES
                        from math import atan2, degrees, sqrt
                        comp_data = [["Line", "Start", "End", "Distance (m)", "Bearing", "Angle"]]

                        for i in range(len(utm_coords)-1):
                            x1, y1 = utm_coords[i]
                            x2, y2 = utm_coords[i+1]

                            dx = x2 - x1
                            dy = y2 - y1

                            distance = sqrt(dx*dx + dy*dy)
                            bearing_rad = atan2(dx, dy)
                            bearing_deg = (degrees(bearing_rad) + 360) % 360

                            angle = "-"  # Placeholder

                            comp_data.append([
                                f"L{i+1}",
                                f"P{i+1}", f"P{i+2}",
                                f"{distance:.2f}",
                                f"{bearing_deg:.2f}°",
                                angle
                            ])

                        comp_table = Table(comp_data, colWidths=[50, 50, 50, 90, 80, 60])
                        comp_table.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                            ('GRID', (0,0), (-1,-1), 1, colors.black),
                            ('ALIGN', (0,0), (-1,-1), 'CENTER')
                        ]))

                        story.append(comp_table)
                        story.append(Spacer(1, 20))

                        doc.build(story)
                        with open(pdf_file, "rb") as f:
                            st.download_button("⬇️ Download Computation Sheet", f, pdf_file, mime="application/pdf")
                    except Exception as e:
                        st.error(f"PDF error: {e}")

        except Exception as e:
                        st.error(f"PDF error: {e}")

        except Exception as e:
            st.error(f"Error: {e}")
after 
