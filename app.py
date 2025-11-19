import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pyproj import Transformer
import pydeck as pdk
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from math import atan2, degrees, sqrt
import io

class DrawPolygon(Flowable):
    def __init__(self, coords, width=400, height=400):
        super().__init__()
        self.coords = coords
        self.width = width
        self.height = height

    def draw(self):
        if not self.coords:
            return
        xs = [c[0] for c in self.coords]
        ys = [c[1] for c in self.coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        scale_x = self.width / (max_x - min_x) if max_x - min_x else 1
        scale_y = self.height / (max_y - min_y) if max_y - min_y else 1
        scale = min(scale_x, scale_y) * 0.8
        offset_x = (self.width - (max_x - min_x) * scale) / 2
        offset_y = (self.height - (max_y - min_y) * scale) / 2
        scaled_coords = [((x - min_x) * scale + offset_x, (y - min_y) * scale + offset_y) for x, y in self.coords]
        self.canv.setStrokeColor(colors.black)
        self.canv.setLineWidth(1)
        for i in range(len(scaled_coords)-1):
            self.canv.line(scaled_coords[i][0], scaled_coords[i][1], scaled_coords[i+1][0], scaled_coords[i+1][1])
        # Close the polygon
        self.canv.line(scaled_coords[-1][0], scaled_coords[-1][1], scaled_coords[0][0], scaled_coords[0][1])

st.set_page_config(page_title="Geo Tools Suite", layout="centered")
st.title("🌍 Geo Tools Suite")

tool = st.sidebar.selectbox("Select a Tool", ["🏠 Home", "Nigeria LGA Finder", "Parcel Plotter"])

if tool == "Parcel Plotter":

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
        st.session_state.parcel_area = polygon.area
        st.success(f"✅ Parcel plotted successfully! Area: {st.session_state.parcel_area:,.2f} m²")

    if st.session_state.parcel_plotted:
        col1, col2 = st.columns(2)

        # Sketch Plan PDF with actual polygon coordinates
        sketch_buffer = io.BytesIO()
        story = [Paragraph("<b>Parcel Sketch Plan</b>", getSampleStyleSheet()['Title']), Spacer(1,12), DrawPolygon(st.session_state.utm_coords)]
        SimpleDocTemplate(sketch_buffer, pagesize=A4).build(story)
        sketch_buffer.seek(0)
        col1.download_button("📄 Print Sketch Plan", data=sketch_buffer.getvalue(), file_name="parcel_sketch_plan.pdf", mime="application/pdf")
