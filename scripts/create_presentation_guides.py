from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageBreak, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, Flowable,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf"
OUT.mkdir(parents=True, exist_ok=True)

NAVY = colors.HexColor("#071A2B")
BLUE = colors.HexColor("#0969DA")
CYAN = colors.HexColor("#00A9C6")
TEAL = colors.HexColor("#028D78")
INK = colors.HexColor("#172033")
MUTED = colors.HexColor("#536174")
PALE = colors.HexColor("#EFF7FB")
ORANGE = colors.HexColor("#D97706")
RED = colors.HexColor("#B42318")


class Rule(Flowable):
    def __init__(self, color=CYAN, width=160):
        Flowable.__init__(self); self.color = color; self.width = width
    def draw(self):
        self.canv.setStrokeColor(self.color); self.canv.setLineWidth(2); self.canv.line(0, 0, self.width, 0)


def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="TitleSea", parent=s["Title"], fontName="Helvetica-Bold", fontSize=29,
                         leading=34, textColor=NAVY, spaceAfter=8))
    s.add(ParagraphStyle(name="SubtitleSea", parent=s["Normal"], fontName="Helvetica", fontSize=12,
                         leading=18, textColor=MUTED, spaceAfter=13))
    s.add(ParagraphStyle(name="H1Sea", parent=s["Heading1"], fontName="Helvetica-Bold", fontSize=18,
                         leading=23, textColor=NAVY, spaceBefore=12, spaceAfter=7))
    s.add(ParagraphStyle(name="H2Sea", parent=s["Heading2"], fontName="Helvetica-Bold", fontSize=12,
                         leading=15, textColor=BLUE, spaceBefore=8, spaceAfter=4))
    s.add(ParagraphStyle(name="BodySea", parent=s["BodyText"], fontName="Helvetica", fontSize=9.4,
                         leading=14, textColor=INK, spaceAfter=6))
    s.add(ParagraphStyle(name="SmallSea", parent=s["BodyText"], fontName="Helvetica", fontSize=8,
                         leading=11, textColor=MUTED, spaceAfter=4))
    s.add(ParagraphStyle(name="Callout", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=10,
                         leading=15, textColor=NAVY, backColor=PALE, borderColor=colors.HexColor("#B9E6F2"),
                         borderWidth=0.7, borderPadding=8, spaceBefore=5, spaceAfter=9))
    s.add(ParagraphStyle(name="Flow", parent=s["BodyText"], fontName="Helvetica-Bold", fontSize=9,
                         leading=12, alignment=TA_CENTER, textColor=colors.white))
    return s


S = styles()

def P(text, style="BodySea"):
    return Paragraph(text, S[style])

def bullet(text):
    return Paragraph("• " + text, S["BodySea"])

def title_page(title, subtitle, badge):
    return [Spacer(1, 35*mm), P("SEALENS", "H2Sea"), Rule(), Spacer(1, 8*mm), P(title, "TitleSea"),
            P(subtitle, "SubtitleSea"), Spacer(1, 8*mm),
            Table([[P(badge, "Callout")]], colWidths=[165*mm], style=[("BOX", (0,0),(-1,-1),0,colors.white)]),
            Spacer(1, 95*mm), P("AI-assisted maritime investigation prototype | Presentation guide", "SmallSea")]

def flow(items):
    cells = [[P(item, "Flow")] for item in items]
    table = Table(cells, colWidths=[165*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), NAVY), ("BOX", (0,0),(-1,-1), .5, colors.white),
        ("INNERGRID", (0,0),(-1,-1), .5, colors.white), ("TOPPADDING",(0,0),(-1,-1),7),
        ("BOTTOMPADDING",(0,0),(-1,-1),7),
    ]))
    return table

def info_table(headers, rows, widths):
    data = [[P(h, "SmallSea") for h in headers]] + [[P(str(x), "SmallSea") for x in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,0), NAVY), ("TEXTCOLOR", (0,0),(-1,0), colors.white),
        ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#CBD5E1")),
        ("BACKGROUND", (0,1),(-1,-1), colors.white),
        ("VALIGN", (0,0),(-1,-1), "TOP"), ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    return t

def build_simple(path):
    story = title_page("SeaLens\nEnd-to-End Project Guide", "A simple, honest explanation of how the prototype detects, traces, and investigates possible marine oil spills.", "What to say in a presentation: SeaLens prioritises follow-up investigation. It does not claim legal proof.")
    story += [PageBreak(), P("1. The problem", "H1Sea"),
              P("An oil slick may be discovered hours after its release. Wind and currents move it, the source can be far away, and many non-oil sea features can look dark in radar imagery. SeaLens brings several evidence streams together so an analyst can decide where to inspect first."),
              P("2. The complete workflow", "H1Sea"), flow(["1. SAR image: find a dark, oil-like candidate and bright radar contacts", "2. Backtrack: reverse the slick through wind and currents in 15-minute steps", "3. Correlate: compare the estimated source area with AIS vessel tracks", "4. Prioritise: rank vessels as investigative leads, not culprits", "5. Report: create a dossier with sources, timestamps, provenance, and uncertainty"]),
              Spacer(1, 8), P("The key design principle", "H2Sea"), P("No single input is trusted alone. SAR suggests a candidate, drift estimates a possible source area, AIS identifies vessels to investigate, and a human reviews the combined evidence."),
              P("3. What SAR does", "H1Sea"),
              P("Synthetic Aperture Radar (SAR) works day or night and through clouds. Oil may damp small waves, so it can appear as a dark region. But low wind, biological slicks, internal waves, and rain can also appear dark. Therefore SeaLens uses the term <b>candidate slick</b> rather than proof of oil.")]
    story += [PageBreak(), P("4. From radar image to candidate slick", "H1Sea"),
              flow(["GeoTIFF SAR crop", "Lee speckle filter reduces grainy radar noise", "U-Net creates a per-pixel slick probability map", "Threshold creates a binary mask", "Contours become georeferenced GeoJSON polygons on the map"]),
              P("In parallel, CA-CFAR searches for unusually bright radar points - possible ships - against the local sea background."),
              P("5. Backtracking the slick", "H1Sea"),
              P("SeaLens begins at the detected slick location and moves backward. It combines current movement with a small wind-driven movement called leeway. The result is an estimated origin <b>area</b>, not an exact point."),
              P("The output is an uncertainty ellipse/cone because wind, current, detection time, and oil shape are imperfect inputs. The uncertainty becomes wider as the backtrack duration increases."),
              P("6. AIS correlation", "H1Sea"),
              P("AIS is a vessel broadcast containing position, speed, course, identity, and status. SeaLens compares vessel tracks with the backtracked source area and scores each vessel using proximity, speed pattern, vessel type, course alignment, and AIS behavioural signals."),
              info_table(["Evidence", "Purpose"], [["Proximity", "How close a vessel passed to the estimated origin"], ["Speed and course", "Whether movement is consistent with the scenario heuristic"], ["Vessel type", "Tanker types receive more investigative relevance"], ["AIS behaviour", "Gaps, sharp turns, or unusual speed changes"]], [48*mm,117*mm])]
    story += [PageBreak(), P("7. Dark-vessel alerts", "H1Sea"), P("A radar contact with no AIS match inside the configured tolerance becomes a dark-vessel candidate. This can mean AIS was off, but it can also be a coverage gap, timing mismatch, position error, or a false radar contact. It is an alert for review, not an accusation."),
              P("8. Response forecasting", "H1Sea"), P("SeaLens can move the slick forward for 72 hours, estimate a possible coastal approach, and calculate simplified weathering - evaporation, emulsification, spreading, and viscosity change. These outputs support planning; they are not an emergency-response authority."),
              P("9. Historical Wakashio case", "H1Sea"), P("The MV Wakashio scenario is a backtest. The real grounding site is already public knowledge. SeaLens asks whether its normal backtrack and vessel-correlation workflow converges towards the known location and stationary vessel using a simulated post-leak observation. This is validation against a known outcome, not mystery solving."),
              P("10. Data provenance - what is real?", "H1Sea"),
              info_table(["Item", "Status", "What it means"], [["Dashboard scenarios", "Synthetic", "Reliable demonstration inputs, not live incidents"], ["Texas Sentinel-1 crop", "Real archived", "A real historical public satellite input"], ["Copernicus current grid", "Real model output", "A scientific gridded model, not an in-water measurement"], ["NOAA AIS path", "Real archived source", "Historical US vessel data when import completes"], ["Fallback drift grid", "Modelled", "Formula-generated offline/demo conditions"]], [45*mm,36*mm,84*mm])]
    story += [PageBreak(), P("11. What the dossier contains", "H1Sea"),
              bullet("Incident and SAR acquisition information"), bullet("Candidate slick area, confidence, orientation, and estimated volume"), bullet("Backtracked origin and uncertainty"), bullet("AIS ranked matches and behavioural observations"), bullet("Data sources, timestamps, cache status, and provenance labels"), bullet("A SHA-256 integrity digest for the generated report"),
              P("12. Honest project status", "H1Sea"),
              P("SeaLens is a complete working prototype, but it is not yet an operational enforcement system. The U-Net runs, but its committed checkpoint has no recorded real-world benchmark metrics. Real archived Sentinel-1 analysis works. Copernicus Marine currents are configured. NOAA AIS at national-archive scale and persistent PostGIS storage are further deployment work."),
              P("Final presentation statement", "H1Sea"), P("SeaLens is a provenance-aware maritime investigation prototype that combines SAR candidate detection, probabilistic drift backtracking, AIS correlation, and uncertainty-aware reporting to prioritise human follow-up.", "Callout")]
    make_pdf(path, story, "SeaLens End-to-End Guide")

def build_technical(path):
    story = title_page("SeaLens\nTechnical Architecture", "Backend, machine learning, data processing, drift physics, AIS correlation, storage, security, and limitations.", "Technical note: descriptions reflect the implemented code. Unverified model training history and planned components are explicitly separated.")
    story += [PageBreak(), P("1. System topology", "H1Sea"), flow(["C2 browser dashboard: frontend/c2.html", "FastAPI API: backend/main.py", "Services: SAR, drift, AIS, met-ocean, reporting", "ML engine: U-Net, GeoTIFF processing, CA-CFAR", "Outputs: JSON, GeoJSON, map overlays, Markdown dossier"]),
              P("At startup, the server loads settings from local `.env`, creates reusable service instances, and tries to load the PyTorch checkpoint at `ml_engine/checkpoints/sar_unet_oil_spill.pt`. It then serves the dashboard at `/c2` and the REST API at `/api/...`."),
              P("2. API and validation", "H1Sea"), P("Pydantic request/data models validate expected fields. Security helpers validate bounding boxes, ISO-style dates, filenames, and allow-listed public asset URLs. The API adds basic rate limiting, security headers, CORS configuration, optional API-key enforcement, audit events, and hashes for downloaded files."),
              P("Important routes", "H2Sea"), info_table(["Route family", "Purpose"], [["/api/scenario/*", "Synthetic and backtest scenario data"], ["/api/real-data/sentinel/*", "Search, crop, and analyse real archived Sentinel-1 RTC inputs"], ["/api/real-data/metocean/*", "GFS/Copernicus subset preparation and backtracking"], ["/api/real-data/noaa-ais/*", "Historical AIS import and correlation"], ["/api/dossier/*", "Markdown forensic dossier"]], [66*mm,99*mm])]
    story += [PageBreak(), P("3. U-Net segmentation model", "H1Sea"), P("Class: `SAROilSpillUNet` in `ml_engine/unet_model.py`. It is a single-channel PyTorch U-Net for per-pixel binary segmentation. The active architecture has 4,317,825 trainable parameters."),
              info_table(["Stage", "Channels / operation"], [["Input", "1 x H x W raster"], ["Encoder", "DoubleConv blocks: 32, 64, 128, 256; max pooling between stages"], ["Bottleneck", "256 channels with bilinear decoder configuration"], ["Decoder", "Bilinear upsampling plus skip-connection concatenation"], ["Output", "1x1 convolution and sigmoid probability [0,1]"]], [50*mm,115*mm]),
              P("Each DoubleConv is 3x3 convolution, BatchNorm, ReLU, then another 3x3 convolution, BatchNorm, ReLU. Skip connections copy early high-resolution features into the decoder, helping preserve thin boundaries."),
              P("Large-raster inference", "H2Sea"), P("Real rasters are tiled into 256x256 windows with 32-pixel overlap. A 2D Hanning window blends overlap areas so that tile edges do not produce visible segmentation seams. The binary mask is thresholded, contoured, and converted to geographical polygons."),
              P("4. Training implementation", "H1Sea"), P("The reproducible trainer `ml_engine/train_sar_unet.py` creates 160 synthetic 256x256 samples. Sea clutter is Gamma-distributed noise. One or two rotated ellipses represent dark, damped oil slicks. Gaussian texture is added. The matching ellipse mask is the label."),
              info_table(["Training setting", "Implemented value"], [["Epochs", "15"], ["Batch size", "8"], ["Optimizer", "AdamW, learning rate 0.001, weight decay 0.0001"], ["Loss", "Binary cross entropy + Dice loss"], ["Output", "Torch checkpoint state dictionary"]], [62*mm,103*mm])]
    story += [PageBreak(), P("5. Model storage and transparency", "H1Sea"), P("Checkpoint location: `ml_engine/checkpoints/sar_unet_oil_spill.pt`. The loader restores `model_state_dict` into a single-channel model and switches it to evaluation mode. A checkpoint normally stores epoch, model weights, final loss, architecture name, input channel count, and class count."),
              P("Critical limitation", "Callout"), P("The exact historical run that produced the committed checkpoint is not fully documented. The included trainer is synthetic. Therefore no claim should be made that the current checkpoint was trained on a named real dataset or achieved a particular real-world accuracy."),
              P("Benchmark framework", "H2Sea"), P("`ml_engine/evaluate_benchmark.py` can compute pixel-level precision, recall, IoU, and false-positive rate after an authorised labelled dataset is downloaded and paired with predictions. The recommended held-out test benchmark is documented in `docs/BENCHMARK_DATA_PLAN.md`; it is not downloaded automatically."),
              P("6. CFAR vessel detector", "H1Sea"), P("`CACFARShipDetector` is a classical radar method, not an ML model. It estimates local sea clutter using an outer training window minus an inner guard window. Its threshold is local clutter mean + 3 x local clutter standard deviation. Bright pixels above threshold are grouped into contours, georeferenced, and given approximate length/beam estimates."),
              P("Default detector parameters: 8 guard cells, 16 training cells, multiplier 3.0, and a raw-intensity floor of 0.65. These are prototype settings and must be calibrated for each real image product."),
              P("7. GeoTIFF pipeline", "H1Sea"), P("Rasterio reads band 1, the code creates a float array, retains the affine transform and bounds, normalises to the 2nd-98th percentile for U-Net inference, applies a 5x5 Lee filter, runs tiled segmentation, and transforms OpenCV contours from pixel coordinates to WGS84 GeoJSON polygons.")]
    story += [PageBreak(), P("8. Drift and met-ocean engine", "H1Sea"), P("`DriftEngine.backtrack_origin()` runs a reverse Lagrangian particle path. It uses 15-minute steps. At each step, it requests a wind/current vector at the particle's current location and previous time, converts it to north/east displacement, then reverses it."),
              P("Basic conceptual equation", "H2Sea"), P("V_slick = V_current + alpha x V_wind, where alpha is 0.032. Wind is converted from the direction it comes from to the direction oil is pushed. Current is supplied as the direction it flows toward."),
              P("Metocean sources", "H2Sea"), info_table(["Source", "Data", "Fallback behaviour"], [["NOAA GFS", "UGRD/VGRD at 10 m; operational forecast only", "Not used for old historical events"], ["Copernicus Marine", "uo/vo surface-current grids", "Used only when credentials and coverage work"], ["DynamicOceanGridEngine", "Formula-generated tide/wind/stokes pattern", "Explicit modelled demo fallback"]], [43*mm,65*mm,57*mm]),
              P("Provider grids are cached in a small incident directory and sampled with bilinear spatial interpolation plus linear time interpolation. The response includes wind source, current source, warnings, and provenance."),
              P("9. AIS pipeline and scoring", "H1Sea"), P("NOAA AIS imports are streamed, Zstandard-decompressed, time/bounding-box filtered, written as a small local CSV, and normalised into VesselTrack/TelemetryPoint objects. The correlation engine finds closest approach to the backtracked origin then scores proximity (35%), speed (15%), vessel type (15%), track alignment (15%), and behavioural signals (20%)."),
              P("Grounded vessels, such as Wakashio, use special stationary-origin logic rather than underway speed/course heuristics.")]
    story += [PageBreak(), P("10. Jobs, storage, security, and report outputs", "H1Sea"), P("Slow SAR crops and AIS imports can run with `background: true`. `LocalJobManager` uses a two-worker `ThreadPoolExecutor` and returns HTTP 202 plus a job ID. The dashboard polls `/api/jobs/{job_id}`. This prevents local UI freezing, but jobs are lost if the server restarts; production needs a durable worker queue."),
              info_table(["Current local storage", "Production target"], [["Scenario objects in Python memory", "PostGIS incident/vessel/spatial tables"], ["SAR/AIS files in local data directories", "Object storage with quotas and lifecycle policy"], ["Job status in process memory", "Durable queue/job store"], ["Run manifests and audit logs as local JSON", "Central immutable audit/observability platform"]], [82*mm,83*mm]),
              P("The PostGIS scaffold creates a `vessel_positions` table with a 4326 point geometry, a GIST spatial index, and MMSI/time index. It is not yet connected to API writes."),
              P("11. Raw SAFE processing", "H1Sea"), P("The included SNAP shell script uses ESA SNAP GPT to apply orbit data, remove thermal noise, calibrate Sigma0, Lee-filter, terrain-correct to EPSG:4326, and export a GeoTIFF. It requires a legitimate downloaded Sentinel-1 GRD SAFE product and visual quality assurance."),
              P("12. Technical conclusion", "H1Sea"), P("The implemented system is a functioning research prototype with a clear migration path. Its strongest engineering characteristics are modular services, explicit data provenance, real-archive ingestion capability, 15-minute dynamic backtracking, and transparent uncertainty. Its main readiness gap is measured validation against a controlled real benchmark and scalable persistent data infrastructure.", "Callout")]
    make_pdf(path, story, "SeaLens Technical Architecture")

def make_pdf(path, story, label):
    def footer(canvas, doc):
        canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D7E3EC")); canvas.line(18*mm, 14*mm, 192*mm, 14*mm)
        canvas.setFont("Helvetica", 7.5); canvas.setFillColor(MUTED)
        canvas.drawString(18*mm, 9*mm, label)
        canvas.drawRightString(192*mm, 9*mm, f"Page {doc.page}")
        canvas.restoreState()
    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=20*mm)
    doc.addPageTemplates([__import__('reportlab.platypus', fromlist=['PageTemplate']).PageTemplate(id='main', frames=[Frame(18*mm,20*mm,174*mm,261*mm,id='normal')], onPage=footer)])
    doc.build(story)

if __name__ == "__main__":
    build_simple(OUT / "SeaLens_End_to_End_Project_Guide.pdf")
    build_technical(OUT / "SeaLens_Technical_Architecture_Guide.pdf")
