import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pyproj import Transformer
import pydeck as pdk
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.graphics import renderPDF
from math import atan2, degrees, sqrt
import io

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

elif tool == "Parcel Plotter":

    if "parcel_plotted" not in st.session_state:
        st.session_state.parcel_plotted = False
    if "parcel_area" not in st.session_state:
        st.session_state.parcel_area = 0

    st.header("📐 Parcel Boundary Plotter (UTM Coordinates)")

    num_points = st.number_input("Number of beacons:", min_value=3, step=1)

    utm_coords = []
    if num_points > 0:
        for i in range(num_points):
            col1, col2 = st.columns(2)
            e = col1.number_input(f"Point {i+1} → Easting (m)", key=f"e{i}", format="%.2f")
            n = col2.number_input(f"Point {i+1} → Northing (m)", key=f"n{i}", format="%.2f")
            utm_coords.append((e, n))

    if st.button("Plot Parcel"):
        if utm_coords[0] != utm_coords[-1]:
            utm_coords.append(utm_coords[0])
        st.session_state.parcel_plotted = True
        st.session_state.utm_coords = utm_coords

        polygon = Polygon(utm_coords)
        if not polygon.is_valid:
            st.error("❌ Invalid boundary shape. Check point sequence.")
        else:
            st.session_state.parcel_area = polygon.area
            st.success(f"✅ Parcel plotted successfully! Area: {st.session_state.parcel_area:,.2f} m²")

    if st.session_state.parcel_plotted:
        if st.button("📄 Print Computation Sheet"):
            try:
                buffer = io.BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=A4)
                styles = getSampleStyleSheet()
                story = []

                story.append(Paragraph("<b>Parcel Computation Sheet</b>", styles['Title']))
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"<b>Total Area:</b> {st.session_state.parcel_area:,.2f} m²", styles['Normal']))
                story.append(Spacer(1, 12))

                coords = st.session_state.utm_coords

                # Compute distances, bearings, angles
                table_data = [["Point ID", "Easting", "Northing", "Distance (m)", "Bearing (°)", "Angle (°)"]]
                n = len(coords)-1

                def compute_distance(p1, p2):
                    return sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

                def compute_bearing(p1, p2):
                    angle = degrees(atan2(p2[0]-p1[0], p2[1]-p1[1]))
                    return (angle + 360) % 360

                for i in range(n):
                    p1 = coords[i]
                    p2 = coords[i+1]
                    dist = compute_distance(p1, p2)
                    bearing = compute_bearing(p1, p2)
                    # Angle at p2 formed by lines (i-1 to i) and (i to i+1)
                    if i == 0:
                        prev = coords[-2]
                    else:
                        prev = coords[i-1]
                    v1x, v1y = p1[0]-prev[0], p1[1]-prev[1]
                    v2x, v2y = p2[0]-p1[0], p2[1]-p1[1]
                    dot = v1x*v2x + v1y*v2y
                    mag1 = sqrt(v1x**2 + v1y**2)
                    mag2 = sqrt(v2x**2 + v2y**2)
                    angle = degrees(acos(dot/(mag1*mag2))) if mag1*mag2 != 0 else 0

                    table_data.append([str(i+1), f"{p1[0]:.2f}", f"{p1[1]:.2f}", f"{dist:.2f}", f"{bearing:.2f}", f"{angle:.2f}"])

                coord_table = Table(table_data, colWidths=[50, 100, 100, 80, 80, 60])
                coord_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                    ('GRID', (0,0), (-1,-1), 1, colors.black),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER')
                ]))

                story.append(coord_table)
                story.append(Spacer(1, 20))

                doc.build(story)
                buffer.seek(0)
                st.download_button("⬇️ Download Computation Sheet", buffer, file_name="parcel_computation_sheet.pdf", mime="application/pdf")

            except Exception as e:
                st.error(f"PDF error: {e}")
