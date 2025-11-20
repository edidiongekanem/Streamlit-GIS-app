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
        # Ensure polygon exists
        if not self.coords or len(self.coords) < 3:
            return

        # Extract UTM coordinates
        xs = [c[0] for c in self.coords]
        ys = [c[1] for c in self.coords]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Normalize (shift polygon to local origin)
        norm_coords = [(x - min_x, y - min_y) for x, y in self.coords]

        width_range = max_x - min_x
        height_range = max_y - min_y

        if width_range == 0:
            width_range = 1
        if height_range == 0:
            height_range = 1

        # Scale
        scale_x = self.width / width_range
        scale_y = self.height / height_range
        scale = min(scale_x, scale_y) * 0.90

        scaled_coords = [
            (x * scale, y * scale) for x, y in norm_coords
        ]

        self.canv.setStrokeColor(colors.black)
        self.canv.setLineWidth(2)

        # Draw polygon edges
        for i in range(len(scaled_coords) - 1):
            x1, y1 = scaled_coords[i]
            x2, y2 = scaled_coords[i + 1]
            self.canv.line(x1, y1, x2, y2)

        # Close polygon
        x1, y1 = scaled_coords[-1]
        x2, y2 = scaled_coords[0]
        self.canv.line(x1, y1, x2, y2)

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

        # Pydeck Map Rendering with Point Labels
        from pyproj import Transformer
        transformer = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
        ll_coords = [transformer.transform(x, y) for x, y in st.session_state.utm_coords]

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
            radius_min_pixels=4,
            radius_max_pixels=20,
        )

        label_data = [
            {"lon": lon, "lat": lat, "text": f"P{i+1}"}
            for i, (lon, lat) in enumerate(ll_coords)
        ]

        text_layer = pdk.Layer(
            "TextLayer",
            label_data,
            get_position="[lon, lat]",
            get_text="text",
            get_size=18,
            get_color="[255, 255, 255]",  # White text
            get_pixel_offset="[10, -10]",  # Slight buffer away from point
            billboard=True,
        )

        centroid_x = sum([c[0] for c in ll_coords]) / len(ll_coords)
        centroid_y = sum([c[1] for c in ll_coords]) / len(ll_coords)

        st.pydeck_chart(
            pdk.Deck(
                layers=[polygon_layer, point_layer, text_layer],
                initial_view_state=pdk.ViewState(
                    longitude=centroid_x,
                    latitude=centroid_y,
                    zoom=18
                ),
                map_style=None
            )
        )

        # Continue with Sketch Plan PDF section
        sketch_buffer = io.BytesIO()
        story = [Paragraph("<b>Parcel Sketch Plan</b>", getSampleStyleSheet()['Title']), Spacer(1,12), DrawPolygon(st.session_state.utm_coords)]
        SimpleDocTemplate(sketch_buffer, pagesize=A4).build(story)
        sketch_buffer.seek(0)
        col1.download_button("📄 Print Sketch Plan", data=sketch_buffer.getvalue(), file_name="parcel_sketch_plan.pdf", mime="application/pdf")
