import streamlit as st
import geopandas as gpd
from shapely.geometry import Point, Polygon
from pyproj import Transformer
import pydeck as pdk
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from math import atan2, degrees, sqrt
import io

# ---------------- Custom Flowables ----------------
class DrawPolygon(Flowable):
    """Draws the polygon, point markers, bearings and distances on the PDF.
    Does NOT rotate the polygon. North arrow will be drawn pointing to point 1.
    """
    def __init__(self, coords, width=160*mm, height=160*mm, show_labels=True):
        super().__init__()
        self.coords = coords
        self.width = float(width)
        self.height = float(height)
        self.show_labels = show_labels

    def draw(self):
        if not self.coords or len(self.coords) < 3:
            return

        xs = [c[0] for c in self.coords]
        ys = [c[1] for c in self.coords]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        # Normalize to origin so UTM values don't go off-page
        norm_coords = [(x - min_x, y - min_y) for x, y in self.coords]

        width_range = max_x - min_x if max_x - min_x != 0 else 1
        height_range = max_y - min_y if max_y - min_y != 0 else 1

        # Fit into box with margin
        margin = 12
        scale_x = (self.width - 2*margin) / width_range
        scale_y = (self.height - 2*margin) / height_range
        scale = min(scale_x, scale_y)

        scaled = [((x * scale) + margin, (y * scale) + margin) for x, y in norm_coords]

        c = self.canv
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)

        # Draw polygon edges
        for i in range(len(scaled)-1):
            x1, y1 = scaled[i]
            x2, y2 = scaled[i+1]
            c.line(x1, y1, x2, y2)
        # Close polygon
        c.line(scaled[-1][0], scaled[-1][1], scaled[0][0], scaled[0][1])

        # Draw point markers and white labels with slight buffer
        if self.show_labels:
            for i, (x, y) in enumerate(scaled[:-1]):
                # marker (filled circle)
                c.setFillColor(colors.black)
                c.circle(x, y, 2, stroke=0, fill=1)
                # draw label (white text over small black halo for contrast)
                label = f"P{i+1}"
                # halo
                c.setFillColor(colors.black)
                c.setFont("Helvetica-Bold", 6)
                c.drawString(x+4-0.5, y+4-0.5, label)
                # white text
                c.setFillColor(colors.white)
                c.drawString(x+4, y+4, label)

        # Draw distances and bearings at edge midpoints
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 6)
        for i in range(len(scaled)-1):
            x1, y1 = scaled[i]
            x2, y2 = scaled[i+1]
            mx, my = (x1 + x2)/2, (y1 + y2)/2
            # compute real-world distance and bearing
            ox1, oy1 = self.coords[i]
            ox2, oy2 = self.coords[i+1]
            dist = sqrt((ox2-ox1)**2 + (oy2-oy1)**2)
            bearing = (degrees(atan2(ox2-ox1, oy2-oy1)) + 360) % 360
            c.drawCentredString(mx, my+6, f"{dist:.2f} m")
            c.drawCentredString(mx, my-6, f"{bearing:.1f}°")

        # Draw north arrow pointing towards point 1 (from centroid)
        try:
            cx = sum([p[0] for p in scaled[:-1]])/ (len(scaled)-1)
            cy = sum([p[1] for p in scaled[:-1]])/ (len(scaled)-1)
            # target is point1
            tx, ty = scaled[0]
            # vector
            vx, vy = tx - cx, ty - cy
            # normalize length for arrow
            length = 30
            # compute unit vector
            mag = (vx**2 + vy**2)**0.5 if (vx**2 + vy**2) != 0 else 1
            ux, uy = vx/mag, vy/mag
            ax, ay = cx + ux*length, cy + uy*length
            # arrow stem
            c.setStrokeColor(colors.black)
            c.setLineWidth(1.2)
            c.line(cx, cy, ax, ay)
            # arrow head
            c.line(ax, ay, ax - uy*6, ay + ux*6)
            c.line(ax, ay, ax + uy*6, ay - ux*6)
            # label N
            c.setFont("Helvetica-Bold", 8)
            c.drawString(ax+6, ay+6, "N")
        except Exception:
            pass

        c.restoreState()

class TitleBlock(Flowable):
    """Creates a simple title block with dotted lines for input text and area in red."""
    def __init__(self, owner_lines=5, area_text="", scale_text="Scale: auto"):
        super().__init__()
        self.owner_lines = owner_lines
        self.area_text = area_text
        self.scale_text = scale_text
        self.w = 180*mm
        self.h = 55*mm

    def draw(self):
        c = self.canv
        c.saveState()
        x0, y0 = 0, 0
        # Header
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x0+10, y0 + self.h - 12, "PLAN SHEWING LANDED PROPERTY")
        c.setFont("Helvetica", 10)
        c.drawString(x0+10, y0 + self.h - 26, "OF")

        # dotted lines for name/location (owner_lines)
        c.setDash(1,2)
        line_y = y0 + self.h - 40
        for i in range(self.owner_lines):
            c.line(x0 + 40, line_y - i*10, x0 + 170, line_y - i*10)
        c.setDash()  # reset

        # scale bar placeholder
        c.rect(x0+10, y0+10, 60, 6, stroke=1, fill=0)
        c.drawString(x0+75, y0+10, self.scale_text)

        # origin and area
        c.drawString(x0+10, y0+26, "ORIGIN: UTM ZONE 32N")
        c.setFillColor(colors.red)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x0+100, y0+26, f"AREA: {self.area_text}")
        c.setFillColor(colors.black)
        c.restoreState()

# ---------------- Streamlit app ----------------
st.set_page_config(page_title="Geo Tools Suite", layout="centered")
st.title("🌍 Geo Tools Suite")

tool = st.sidebar.selectbox("Select a Tool", ["🏠 Home", "Nigeria LGA Finder", "Parcel Plotter"]) 

if tool == "🏠 Home":
    st.header("Welcome!")
    st.write("""
    Select any of the tools from the sidebar:
    
    ### 🗺️ Nigeria LGA Finder  
    Enter Easting/Northing and find which LGA the point belongs to.
    
    ### 📐 Parcel Plotter  
    Input coordinates, plot a parcel boundary and calculate the area.
    """)

# Nigeria LGA Finder (unchanged)
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
            polygon_layer = pdk.Layer("PolygonLayer", polygon_data, get_polygon="coordinates", get_fill_color="[0, 120, 255, 60]", get_line_color="[0, 80, 200]", stroked=True)
            point_layer = pdk.Layer("ScatterplotLayer", [{"lon": lon, "lat": lat}], get_position="[lon, lat]", get_color="[255, 0, 0]", radius_scale=1, radius_min_pixels=5, radius_max_pixels=40)
            centroid = Point(lon, lat)
            st.pydeck_chart(pdk.Deck(layers=[polygon_layer, point_layer], initial_view_state=pdk.ViewState(latitude=centroid.y, longitude=centroid.x, zoom=10), map_style=None))
        else:
            st.error("❌ No LGA found for this location.")

# Parcel Plotter
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
        st.session_state.parcel_area = polygon.area
        st.success(f"✅ Parcel plotted successfully! Area: {st.session_state.parcel_area:,.2f} m²")

    if st.session_state.parcel_plotted:
        col1, col2 = st.columns(2)

        # Pydeck map with point labels
        transformer = Transformer.from_crs("EPSG:32632", "EPSG:4326", always_xy=True)
        ll_coords = [transformer.transform(x, y) for x, y in st.session_state.utm_coords]
        polygon_data = [{"coordinates": [ll_coords]}]
        polygon_layer = pdk.Layer("PolygonLayer", polygon_data, get_polygon="coordinates", get_fill_color="[0, 150, 255, 80]", get_line_color="[0, 50, 200]", stroked=True)
        point_layer = pdk.Layer("ScatterplotLayer", [{"lon": lon, "lat": lat} for lon, lat in ll_coords], get_position="[lon, lat]", get_color="[255, 0, 0]", radius_scale=1, radius_min_pixels=4, radius_max_pixels=20)
        label_data = [{"lon": lon, "lat": lat, "text": f"P{i+1}"} for i, (lon, lat) in enumerate(ll_coords)]
        text_layer = pdk.Layer("TextLayer", label_data, get_position="[lon, lat]", get_text="text", get_size=18, get_color="[255, 255, 255]", get_pixel_offset="[12, -12]", billboard=True)
        centroid_x = sum([c[0] for c in ll_coords]) / len(ll_coords)
        centroid_y = sum([c[1] for c in ll_coords]) / len(ll_coords)
        st.pydeck_chart(pdk.Deck(layers=[polygon_layer, point_layer, text_layer], initial_view_state=pdk.ViewState(longitude=centroid_x, latitude=centroid_y, zoom=18), map_style=None))

        # Build Sketch Plan PDF
        sketch_buffer = io.BytesIO()
        area_str = f"{st.session_state.parcel_area:,.2f} m²"
        tb = TitleBlock(owner_lines=5, area_text=area_str, scale_text="Scale: auto")
        story = [tb, Spacer(1,8), DrawPolygon(st.session_state.utm_coords)]
        SimpleDocTemplate(sketch_buffer, pagesize=A4).build(story)
        sketch_buffer.seek(0)
        col1.download_button("📄 Print Sketch Plan", data=sketch_buffer.getvalue(), file_name="parcel_sketch_plan.pdf", mime="application/pdf")

        # Build Computation Sheet PDF
        comp_buffer = io.BytesIO()
        story2 = [Paragraph("<b>Parcel Computation Sheet</b>", getSampleStyleSheet()['Title']), Spacer(1,12), Paragraph(f"<b>Total Area:</b> {st.session_state.parcel_area:,.2f} m²", getSampleStyleSheet()['Normal']), Spacer(1,12)]
        coords = st.session_state.utm_coords
        if coords and len(coords) > 1:
            table_data = [["Point ID", "Easting", "Northing", "Distance (m)", "Bearing (°)", "Angle (°)"]]
            def compute_distance(p1,p2): return sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
            def compute_bearing(p1,p2): return (degrees(atan2(p2[0]-p1[0],p2[1]-p1[1]))+360)%360
            n = len(coords)-1
            bearings = []
            for i in range(n):
                p1,p2=coords[i],coords[i+1]
                dist=compute_distance(p1,p2)
                bearing=compute_bearing(p1,p2)
                bearings.append(bearing)
                table_data.append([str(i+1), f"{p1[0]:.2f}", f"{p1[1]:.2f}", f"{dist:.2f}", f"{bearing:.2f}", ""])
            for i in range(1,n):
                table_data[i][5]=f"{(bearings[i]-bearings[i-1])%360:.2f}"
            coord_table=Table(table_data, colWidths=[50,90,90,80,80,60])
            coord_table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('GRID',(0,0),(-1,-1),1,colors.black),('ALIGN',(0,0),(-1,-1),'CENTER')]))
            story2.append(coord_table)
            story2.append(Spacer(1,20))
        SimpleDocTemplate(comp_buffer,pagesize=A4).build(story2)
        comp_buffer.seek(0)
        col2.download_button("📄 Print Computation Sheet", data=comp_buffer.getvalue(), file_name="parcel_computation_sheet.pdf", mime="application/pdf")
