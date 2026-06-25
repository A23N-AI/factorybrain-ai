from datetime import datetime
from io import BytesIO
import uuid

import fitz
import pandas as pd
import plotly.express as px
import streamlit as st


CATEGORIES = [
    "SOP",
    "Maintenance Log",
    "Shift Report",
    "Defect Report",
    "Safety Checklist",
    "Machine Manual",
    "Other",
]


TROUBLESHOOTING_PLACEHOLDER = "Select a manufacturing situation"


# These predefined rules keep the page honest and local-only.
# The typed observation note is not analyzed by AI or saved anywhere.
TROUBLESHOOTING_GUIDANCE = {
    "Strip tracking or alignment deviation": {
        "attention": (
            "Strip movement away from the expected path can create quality risk, "
            "edge damage, line instability, or equipment contact if it continues. "
            "The goal is safe observation and escalation, not guessing the root cause."
        ),
        "safe_actions": [
            "Stay in the approved operating area and observe strip position only from a safe distance.",
            "Do not reach near moving strip, rotating rolls, guides, or steering equipment.",
            "Follow the active operating SOP if the strip position appears unsafe or unstable.",
            "Stop or slow the process only according to site procedure and authorization.",
        ],
        "checks": [
            "Record which stand, guide, steering unit, or line area appears involved.",
            "Check visible guide or steering indicators only if you are authorized to do so.",
            "Compare the current line condition with the applicable operating SOP.",
            "Look for visible alarms or operator display messages related to tracking.",
        ],
        "record": [
            "Time of issue",
            "Mill stand, guide, steering unit, or line area",
            "Coil number or production order",
            "Process speed or operating condition",
            "Visible strip position or edge condition",
        ],
        "escalation": (
            "Escalate to the shift supervisor first. Contact the production engineer "
            "or maintenance team if the condition continues, affects quality, or "
            "could damage equipment."
        ),
        "keywords": [
            "strip tracking",
            "alignment",
            "guide roll",
            "steering",
            "edge damage",
        ],
    },
    "Surface scratches or visible strip defects": {
        "attention": (
            "Visible strip defects may affect customer quality, rework decisions, "
            "or material release. The first response should protect traceability "
            "and prevent more affected material from moving forward unnoticed."
        ),
        "safe_actions": [
            "Identify or hold affected material according to the site quality procedure.",
            "Do not touch moving strip or inspect near rotating equipment.",
            "Use normal safe viewing points and approved inspection methods only.",
            "Notify the appropriate operator or supervisor if the defect appears severe or spreading.",
        ],
        "checks": [
            "Record the visible defect pattern, direction, and approximate strip location.",
            "Check cleanliness or visible contamination only from a safe position and only if authorized.",
            "Compare the defect with the applicable quality checklist or inspection SOP.",
            "Check whether the same pattern appears across the coil, at edges, or at intervals.",
        ],
        "record": [
            "Time of observation",
            "Coil or batch reference",
            "Surface side, edge, center, or full-width location",
            "Defect pattern, length, and repeat behavior",
            "Inspection station or line area",
        ],
        "escalation": (
            "Escalate to the quality team and shift supervisor. Include the production "
            "engineer when the defect may be linked to process conditions."
        ),
        "keywords": [
            "surface defect",
            "scratch",
            "contamination",
            "quality hold",
            "strip defect",
        ],
    },
    "Thickness variation or out-of-tolerance strip": {
        "attention": (
            "Thickness variation can affect product specification, customer acceptance, "
            "and downstream processing. The first response is to preserve measured "
            "evidence and compare it with the active order requirements."
        ),
        "safe_actions": [
            "Follow the site quality procedure for identifying or holding affected material.",
            "Do not adjust process settings unless you are trained and authorized.",
            "Avoid working near moving strip or energized equipment while checking information.",
            "Escalate promptly if readings are outside tolerance or changing quickly.",
        ],
        "checks": [
            "Record measured values and the tolerance limits from the active order.",
            "Check process settings against the active order or SOP only if authorized.",
            "Check whether the variation is continuous, sudden, or linked to a coil section.",
            "Review visible gauge, control display, or alarm messages without bypassing controls.",
        ],
        "record": [
            "Time and measurement location",
            "Measured thickness values",
            "Specified tolerance limits",
            "Coil, batch, or order reference",
            "Relevant process condition or control display",
        ],
        "escalation": (
            "Escalate to the shift supervisor, production engineer, and quality team. "
            "Contact maintenance if equipment condition or sensor reliability may need review."
        ),
        "keywords": [
            "thickness",
            "gauge",
            "tolerance",
            "out of tolerance",
            "process setting",
        ],
    },
    "Abnormal vibration or unusual noise": {
        "attention": (
            "New or abnormal vibration and noise can signal a condition that may affect "
            "equipment reliability or operator safety. The response should focus on "
            "keeping people clear and recording what changed."
        ),
        "safe_actions": [
            "Stop or secure equipment according to site procedure if the condition appears unsafe.",
            "Do not touch rotating, energized, or moving components.",
            "Keep clear of the affected area and avoid standing near guarded moving equipment.",
            "Report the condition before attempting any reset, restart, or adjustment.",
        ],
        "checks": [
            "Record the time, machine area, operating speed, load, and product condition.",
            "Check visible alarms or status indicators from the normal operator position.",
            "Look for loose external guards or panels only from a safe position and only if authorized.",
            "Compare the condition with the applicable operating or maintenance SOP.",
        ],
        "record": [
            "Time when vibration or noise started",
            "Machine or line area",
            "Operating speed, load, or process condition",
            "Sound or vibration pattern",
            "Alarm message or display if present",
        ],
        "escalation": (
            "Escalate to the shift supervisor and maintenance team. Treat the situation "
            "as urgent if vibration increases, guarding is affected, or people may be at risk."
        ),
        "keywords": [
            "vibration",
            "noise",
            "bearing",
            "roll",
            "motor",
        ],
    },
    "Hydraulic or lubrication leak / pressure concern": {
        "attention": (
            "Fluid leaks and pressure concerns can create slip hazards, fire risk, "
            "equipment damage, or injury from hot or pressurized fluid. Keep the "
            "response focused on isolation, containment, and escalation under site rules."
        ),
        "safe_actions": [
            "Do not touch hot, pressurized, or leaking fluid.",
            "Keep clear of possible spray, mist, puddles, and slip hazards.",
            "Follow the site containment and isolation procedure if trained and authorized.",
            "Stop work and escalate immediately if people, equipment, or the environment may be at risk.",
        ],
        "checks": [
            "Record the visible leak location without approaching unsafe areas.",
            "Check visible pressure readings, level indicators, or alarms only if authorized.",
            "Look for spread of fluid on floors, guards, or nearby equipment from a safe position.",
            "Compare the condition with the relevant hydraulic or lubrication SOP.",
        ],
        "record": [
            "Time the leak or pressure concern was noticed",
            "Machine area and visible leak location",
            "Fluid type if known from safe labeling or display",
            "Pressure reading, level reading, or alarm message",
            "Any slip, spray, heat, or containment concern",
        ],
        "escalation": (
            "Escalate to the shift supervisor and maintenance team. Contact the safety "
            "representative when there is a spill, slip risk, spray risk, or required isolation."
        ),
        "keywords": [
            "hydraulic",
            "lubrication",
            "leak",
            "pressure",
            "lockout",
        ],
    },
    "High roll, bearing, motor, or cooling-temperature concern": {
        "attention": (
            "High temperature readings can affect equipment reliability, product quality, "
            "and operator safety. Treat the reading as an important warning sign that "
            "needs controlled checking and escalation."
        ),
        "safe_actions": [
            "Do not touch hot rolls, bearings, motors, pipes, or guards.",
            "Stay in approved walkways and avoid heat, steam, fluid, or moving equipment hazards.",
            "Follow the site procedure if temperature alarms are active or rising.",
            "Do not remove covers, open equipment, or adjust cooling systems unless authorized.",
        ],
        "checks": [
            "Check visible temperature indicators or alarm displays only if authorized.",
            "Check visible cooling flow or lubrication indicators from a safe position.",
            "Record the machine area, temperature value, operating load, and production condition.",
            "Compare the reading with the applicable SOP or operating limit.",
        ],
        "record": [
            "Time of high-temperature concern",
            "Roll, bearing, motor, or cooling area involved",
            "Temperature value and display source",
            "Operating speed, load, or product condition",
            "Cooling or lubrication alarm if present",
        ],
        "escalation": (
            "Escalate to the shift supervisor and maintenance team. Include production "
            "engineering if the concern may affect process stability or product quality."
        ),
        "keywords": [
            "temperature",
            "bearing",
            "motor",
            "cooling",
            "lubrication",
        ],
    },
    "Unexpected machine stoppage or control alarm": {
        "attention": (
            "An unexpected stoppage or control alarm can involve safety, quality, "
            "process, or equipment reliability risk. The first response is to keep "
            "the area safe and preserve exact alarm information."
        ),
        "safe_actions": [
            "Keep people clear of moving equipment and any stored-energy hazards.",
            "Do not repeatedly reset alarms or bypass controls.",
            "Follow the relevant operating SOP before restarting or clearing the alarm.",
            "Stop and escalate if the alarm message involves safety, guarding, pressure, or heat.",
        ],
        "checks": [
            "Record the exact alarm text, code, screen, and time shown on the display.",
            "Check the current machine state from the normal operator position.",
            "Compare the alarm with the applicable SOP or alarm response sheet.",
            "Confirm whether material, speed, temperature, pressure, or guarding status changed.",
        ],
        "record": [
            "Exact alarm text or code",
            "Time of stoppage",
            "Machine area and operator screen",
            "Coil, batch, or process condition",
            "Action taken before and after the alarm",
        ],
        "escalation": (
            "Escalate to the shift supervisor. Contact maintenance or controls support "
            "through the site process when the alarm cannot be cleared safely or repeats."
        ),
        "keywords": [
            "alarm",
            "control alarm",
            "machine stoppage",
            "reset",
            "SOP",
        ],
    },
    "Safety, guarding, or unsafe-condition concern": {
        "attention": (
            "A safety, guarding, or unsafe-condition concern can place people at "
            "immediate risk. Production or quality targets should never override "
            "site safety rules."
        ),
        "safe_actions": [
            "Stop work or halt the process where required by site procedure.",
            "Do not bypass guards, interlocks, emergency stops, or safety devices.",
            "Keep people clear of the affected area.",
            "Treat imminent danger as an emergency under site rules.",
        ],
        "checks": [
            "Check visible indicators or alarm messages only from a safe position.",
            "Confirm the affected area, guard, access point, or unsafe condition.",
            "Compare the situation with the applicable safety SOP or permit requirement.",
            "Use lockout/tagout only according to your training and official site procedure.",
        ],
        "record": [
            "Time and location of the unsafe condition",
            "People or work area affected",
            "Guard, interlock, access point, or hazard involved",
            "Alarm message, emergency stop status, or site report reference",
            "Immediate action taken to keep people clear",
        ],
        "escalation": (
            "Report immediately to the shift supervisor and safety representative. "
            "Contact maintenance only through the approved site safety and isolation process."
        ),
        "keywords": [
            "safety",
            "guarding",
            "interlock",
            "lockout",
            "unsafe condition",
        ],
    },
}


def get_file_extension(file_name):
    """Return the file extension without the dot."""
    if "." not in file_name:
        return ""

    return file_name.rsplit(".", 1)[-1].lower()


def show_file_details(uploaded_file, selected_category, file_extension):
    """Show simple details about the uploaded file."""
    file_size_kb = uploaded_file.size / 1024

    st.markdown("### File details")
    st.write(f"**File name:** {uploaded_file.name}")
    st.write(f"**File type:** {file_extension.upper()}")
    st.write(f"**Selected category:** {selected_category}")
    st.write(f"**File size:** {file_size_kb:.2f} KB")


def get_file_size_display(file_size_bytes):
    """Return a friendly file size for non-technical users."""
    file_size_kb = file_size_bytes / 1024
    return f"{file_size_kb:.2f} KB"


def preview_txt_file(file_bytes):
    """Preview text from a TXT file."""
    text_preview = file_bytes.decode("utf-8")

    if not text_preview.strip():
        st.warning("This TXT file is empty or does not contain readable text.")
        return False

    st.text_area("TXT preview", text_preview[:3000], height=250)
    return True


def preview_csv_file(file_bytes):
    """Preview the first five rows from a CSV file."""
    data_frame = pd.read_csv(BytesIO(file_bytes), nrows=5)

    if data_frame.empty:
        st.warning("This CSV file opened, but it does not contain previewable rows.")
        return False

    st.dataframe(data_frame, width="stretch")
    return True


def preview_excel_file(file_bytes):
    """Preview the first five rows from the first worksheet in an Excel file."""
    data_frame = pd.read_excel(BytesIO(file_bytes), sheet_name=0, nrows=5)

    if data_frame.empty:
        st.warning("This Excel file opened, but the first worksheet has no previewable rows.")
        return False

    st.dataframe(data_frame, width="stretch")
    return True


def preview_pdf_file(file_bytes):
    """Preview extracted text from the first page of a PDF file."""
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")

    if pdf_document.page_count == 0:
        st.warning("This PDF opened, but it does not contain any pages.")
        pdf_document.close()
        return False

    first_page = pdf_document.load_page(0)
    page_text = first_page.get_text()
    pdf_document.close()

    if not page_text.strip():
        st.warning("The first PDF page does not contain extractable text.")
        return False

    st.text_area("PDF first-page text preview", page_text[:3000], height=250)
    return True


def show_file_preview(uploaded_file, file_extension):
    """Show a temporary preview for supported local file types."""
    file_bytes = uploaded_file.getvalue()

    if len(file_bytes) == 0:
        st.error("This file is empty. Please choose a file with content to preview.")
        return False

    st.markdown("### Temporary preview")

    try:
        if file_extension == "txt":
            return preview_txt_file(file_bytes)
        elif file_extension == "csv":
            return preview_csv_file(file_bytes)
        elif file_extension in ("xlsx", "xls"):
            return preview_excel_file(file_bytes)
        elif file_extension == "pdf":
            return preview_pdf_file(file_bytes)
        else:
            st.error("This file type is not supported in the temporary preview.")
            return False
    except UnicodeDecodeError:
        st.error("This TXT file could not be read as plain UTF-8 text.")
        return False
    except Exception:
        st.error(
            "This file could not be previewed. It may be damaged, unreadable, "
            "password-protected, or saved in an unexpected format."
        )
        return False


def initialize_document_collection():
    """Create the temporary session collection only when it does not exist yet."""
    if "document_collection" not in st.session_state:
        # This list is session-only. It is not saved to disk or any database.
        st.session_state["document_collection"] = []


def extract_txt_text(file_bytes):
    """Extract readable text from a TXT file."""
    return file_bytes.decode("utf-8")


def extract_csv_text(file_bytes):
    """Convert CSV headers and rows into simple searchable text."""
    data_frame = pd.read_csv(BytesIO(file_bytes))
    return data_frame.to_csv(index=False)


def extract_excel_text(file_bytes):
    """Convert the first Excel worksheet into simple searchable text."""
    data_frame = pd.read_excel(BytesIO(file_bytes), sheet_name=0)
    return data_frame.to_csv(index=False)


def extract_pdf_text(file_bytes):
    """Extract readable text from all PDF pages that contain text."""
    pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
    page_texts = []

    try:
        for page_number in range(pdf_document.page_count):
            page = pdf_document.load_page(page_number)
            page_texts.append(page.get_text())
    finally:
        pdf_document.close()

    return "\n".join(page_texts)


def extract_text_for_collection(file_bytes, file_extension):
    """Get usable text for the future local search feature."""
    if file_extension == "txt":
        return extract_txt_text(file_bytes)
    if file_extension == "csv":
        return extract_csv_text(file_bytes)
    if file_extension in ("xlsx", "xls"):
        return extract_excel_text(file_bytes)
    if file_extension == "pdf":
        return extract_pdf_text(file_bytes)

    return ""


def get_preview_summary(extracted_text):
    """Create a short readable summary from the stored text."""
    clean_text = " ".join(extracted_text.split())

    if not clean_text:
        return "No extractable text was found."

    return clean_text[:300]


def clean_text_for_display(text):
    """Remove extra spaces and line breaks so text is easier to read."""
    return " ".join(text.split())


def create_search_snippet(document_text, search_phrase, context_characters=120):
    """Create a short snippet around the first matching keyword or phrase."""
    lowercase_text = document_text.lower()
    lowercase_search_phrase = search_phrase.lower()
    match_start = lowercase_text.find(lowercase_search_phrase)

    if match_start == -1:
        return ""

    match_end = match_start + len(search_phrase)
    snippet_start = max(0, match_start - context_characters)
    snippet_end = min(len(document_text), match_end + context_characters)

    before_match = clean_text_for_display(document_text[snippet_start:match_start])
    matched_text = clean_text_for_display(document_text[match_start:match_end])
    after_match = clean_text_for_display(document_text[match_end:snippet_end])

    snippet_parts = []

    if snippet_start > 0:
        snippet_parts.append("...")

    if before_match:
        snippet_parts.append(before_match)

    # The match marker keeps the search result understandable without complex UI.
    snippet_parts.append(f"[match: {matched_text}]")

    if after_match:
        snippet_parts.append(after_match)

    if snippet_end < len(document_text):
        snippet_parts.append("...")

    return " ".join(snippet_parts)


def find_matching_documents(documents, search_phrase):
    """Find documents where the stored extracted text contains the search phrase."""
    matching_documents = []
    lowercase_search_phrase = search_phrase.lower()

    for document in documents:
        extracted_text = document["extracted_text"]

        if lowercase_search_phrase in extracted_text.lower():
            matching_documents.append(
                {
                    "document": document,
                    "snippet": create_search_snippet(extracted_text, search_phrase),
                }
            )

    return matching_documents


def has_extracted_text(document):
    """Check whether a document has stored extracted text available."""
    extracted_text = document.get("extracted_text", "")
    return bool(str(extracted_text).strip())


def get_document_file_type(document):
    """Derive a readable file type from the stored file name."""
    file_name = document.get("file_name", "")
    file_extension = get_file_extension(file_name)

    if file_extension:
        return file_extension.upper()

    return "Unknown"


def get_document_file_size(document):
    """Return the stored file size display, with a safe fallback."""
    if document.get("file_size_display"):
        return document["file_size_display"]

    if document.get("file_size_bytes") is not None:
        return get_file_size_display(document["file_size_bytes"])

    return "Not available"


def build_document_inventory_rows(documents):
    """Build simple table rows for the Maintenance Insights inventory."""
    inventory_rows = []

    for document in documents:
        inventory_rows.append(
            {
                "File Name": document.get("file_name", "Unknown file"),
                "Category": document.get("category", "Uncategorized"),
                "File Type": get_document_file_type(document),
                "File Size": get_document_file_size(document),
                "Extracted Text Available": "Yes" if has_extracted_text(document) else "No",
            }
        )

    return inventory_rows


def get_export_file_size_bytes(document):
    """Return file size bytes as a number for the export inventory."""
    file_size_bytes = document.get("file_size_bytes", 0)

    try:
        return int(file_size_bytes)
    except (TypeError, ValueError):
        return 0


def get_extracted_text_length(document):
    """Return the stored extracted text length, or 0 when no text is available."""
    extracted_text = str(document.get("extracted_text", ""))

    if not extracted_text.strip():
        return 0

    return len(extracted_text)


def build_export_inventory_data_frame(documents):
    """Build the one-row-per-document inventory used by Export Report."""
    columns = [
        "File Name",
        "Category",
        "File Type",
        "File Size (Bytes)",
        "File Size (KB)",
        "Extracted Text Available",
        "Extracted Text Length (Characters)",
    ]
    inventory_rows = []

    for document in documents:
        file_size_bytes = get_export_file_size_bytes(document)

        inventory_rows.append(
            {
                "File Name": document.get("file_name", "Unknown file"),
                "Category": document.get("category", "Uncategorized"),
                "File Type": get_document_file_type(document),
                "File Size (Bytes)": file_size_bytes,
                "File Size (KB)": round(file_size_bytes / 1024, 2),
                "Extracted Text Available": "Yes" if has_extracted_text(document) else "No",
                "Extracted Text Length (Characters)": get_extracted_text_length(document),
            }
        )

    return pd.DataFrame(inventory_rows, columns=columns)


def calculate_export_summary_metrics(documents):
    """Calculate simple export metrics from the selected documents only."""
    represented_categories = set()
    represented_file_types = set()
    documents_with_text = 0

    for document in documents:
        represented_categories.add(document.get("category", "Uncategorized"))
        represented_file_types.add(get_document_file_type(document))

        if has_extracted_text(document):
            documents_with_text += 1

    return {
        "documents_included": len(documents),
        "categories_represented": len(represented_categories),
        "file_types_represented": len(represented_file_types),
        "documents_with_text": documents_with_text,
        "documents_without_text": len(documents) - documents_with_text,
    }


def build_category_breakdown_data_frame(documents):
    """Build a small category count table for the selected export scope."""
    category_counts = {}

    for document in documents:
        category = document.get("category", "Uncategorized")
        category_counts[category] = category_counts.get(category, 0) + 1

    rows = [
        {
            "Category": category,
            "Documents Included": document_count,
        }
        for category, document_count in category_counts.items()
    ]

    return pd.DataFrame(rows, columns=["Category", "Documents Included"]).sort_values(
        ["Documents Included", "Category"],
        ascending=[False, True],
    )


def build_export_summary_data_frame(export_scope, selected_category, metrics):
    """Build the one-row summary CSV for the selected export scope."""
    columns = [
        "Export Scope",
        "Selected Category",
        "Documents Included",
        "Categories Represented",
        "File Types Represented",
        "Documents with Extracted Text Available",
        "Documents without Extracted Text Available",
        "Generated Locally At",
    ]
    summary_row = {
        "Export Scope": export_scope,
        "Selected Category": selected_category,
        "Documents Included": metrics["documents_included"],
        "Categories Represented": metrics["categories_represented"],
        "File Types Represented": metrics["file_types_represented"],
        "Documents with Extracted Text Available": metrics["documents_with_text"],
        "Documents without Extracted Text Available": metrics["documents_without_text"],
        "Generated Locally At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    return pd.DataFrame([summary_row], columns=columns)


def make_safe_filename_part(text):
    """Create a simple file-name-safe version of a category name."""
    safe_characters = []

    for character in text.lower():
        if character.isalnum():
            safe_characters.append(character)
        else:
            safe_characters.append("_")

    safe_name = "_".join("".join(safe_characters).split("_"))

    if safe_name:
        return safe_name

    return "category"


def escape_spreadsheet_formula_value(value):
    """Prevent spreadsheet apps from treating exported text as a formula."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value

    return value


def convert_data_frame_to_safe_csv(data_frame):
    """Convert a DataFrame to Excel-friendly CSV bytes without changing app data."""
    safe_data_frame = data_frame.copy()

    for column_name in safe_data_frame.columns:
        safe_data_frame[column_name] = safe_data_frame[column_name].map(
            escape_spreadsheet_formula_value
        )

    return safe_data_frame.to_csv(index=False).encode("utf-8-sig")


def is_duplicate_document(file_name, selected_category, file_size_bytes):
    """Check duplicates using file name, category, and file size."""
    for document in st.session_state["document_collection"]:
        same_file_name = document["file_name"] == file_name
        same_category = document["category"] == selected_category
        same_file_size = document["file_size_bytes"] == file_size_bytes

        if same_file_name and same_category and same_file_size:
            return True

    return False


def add_document_to_collection(uploaded_file, selected_category, file_extension):
    """Add one uploaded file's text and metadata to the session collection."""
    file_bytes = uploaded_file.getvalue()

    if is_duplicate_document(uploaded_file.name, selected_category, uploaded_file.size):
        st.warning("This document is already in the current session collection.")
        return

    try:
        extracted_text = extract_text_for_collection(file_bytes, file_extension)
    except UnicodeDecodeError:
        st.error("This TXT file could not be added because it is not readable as UTF-8 text.")
        return
    except Exception:
        st.error(
            "This document could not be added. It may be damaged, unreadable, "
            "password-protected, or saved in an unexpected format."
        )
        return

    if not extracted_text.strip():
        st.warning("This document did not contain extractable text, so it was not added.")
        return

    # Each collection item stores metadata plus extracted text, not the raw upload.
    document = {
        "document_id": str(uuid.uuid4()),
        "file_name": uploaded_file.name,
        "file_type": file_extension.upper(),
        "category": selected_category,
        "file_size_bytes": uploaded_file.size,
        "file_size_display": get_file_size_display(uploaded_file.size),
        "extracted_text": extracted_text,
        "preview_summary": get_preview_summary(extracted_text),
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    st.session_state["document_collection"].append(document)
    st.success("Document added to the current session collection.")


def show_collection_messages():
    """Show success messages created before a Streamlit rerun."""
    message = st.session_state.pop("collection_message", None)

    if message:
        st.success(message)


def remove_document_from_collection(document_id):
    """Remove one document and keep the rest of the collection unchanged."""
    st.session_state["document_collection"] = [
        document
        for document in st.session_state["document_collection"]
        if document["document_id"] != document_id
    ]
    st.session_state["collection_message"] = "Document removed from the current session collection."
    st.rerun()


def clear_document_collection():
    """Clear all session-only collection data."""
    st.session_state["document_collection"] = []
    st.session_state["collection_message"] = "Entire current session collection cleared."
    st.rerun()


def show_current_session_collection():
    """Show the temporary documents collected during this browser session."""
    st.subheader("Current Session Collection")
    st.info(
        "Documents in this collection exist only during the current browser session. "
        "They are not saved permanently or stored in the project folder."
    )

    documents = st.session_state["document_collection"]
    st.write(f"**Total documents:** {len(documents)}")

    if not documents:
        st.write("No documents have been added to the current session collection yet.")
        return

    table_rows = []
    for document in documents:
        table_rows.append(
            {
                "File Name": document["file_name"],
                "File Type": document["file_type"],
                "Category": document["category"],
                "File Size": document["file_size_display"],
                "Added At": document["added_at"],
            }
        )

    st.dataframe(pd.DataFrame(table_rows), width="stretch", hide_index=True)

    for document in documents:
        expander_label = f"{document['file_name']} ({document['category']})"

        with st.expander(expander_label):
            st.write(f"**Document ID:** {document['document_id']}")
            st.write(f"**File name:** {document['file_name']}")
            st.write(f"**File type:** {document['file_type']}")
            st.write(f"**Category:** {document['category']}")
            st.write(f"**File size:** {document['file_size_display']}")
            st.write(f"**Added at:** {document['added_at']}")
            st.text_area(
                "Stored text preview",
                document["preview_summary"],
                height=140,
                key=f"stored_text_preview_{document['document_id']}",
            )

            if st.button(
                "Remove Document",
                key=f"remove_document_{document['document_id']}",
            ):
                remove_document_from_collection(document["document_id"])

    st.warning(
        "This removes all documents from the current session only and cannot be undone."
    )

    if st.button("Clear Entire Collection"):
        clear_document_collection()


def show_upload_knowledge_page():
    """Show the temporary upload and preview page."""
    initialize_document_collection()
    show_collection_messages()

    st.title("Upload Knowledge")
    st.write(
        "Upload one local manufacturing knowledge file and preview it during this "
        "Streamlit session."
    )

    st.warning(
        "Temporary preview only: uploaded files are not saved permanently and are not "
        "stored in the project folder."
    )

    selected_category = st.selectbox(
        "Choose one knowledge category",
        CATEGORIES,
    )

    uploaded_file = st.file_uploader(
        "Choose one local file",
        type=["txt", "csv", "xlsx", "xls", "pdf"],
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        st.info("Choose a TXT, CSV, Excel, or PDF file to see a temporary preview.")
        st.divider()
        show_current_session_collection()
        return

    file_extension = get_file_extension(uploaded_file.name)
    show_file_details(uploaded_file, selected_category, file_extension)
    preview_was_successful = show_file_preview(uploaded_file, file_extension)

    if preview_was_successful:
        if st.button("Add Document to Collection"):
            add_document_to_collection(uploaded_file, selected_category, file_extension)

    st.divider()
    show_current_session_collection()


def show_search_factory_brain_page():
    """Show basic keyword search for the current session document collection."""
    initialize_document_collection()

    st.title("Search Factory Brain")
    st.write(
        "Use this basic local keyword search to look inside documents that are "
        "currently stored in the temporary in-session collection."
    )

    documents = st.session_state["document_collection"]

    if not documents:
        st.info(
            "Your document collection is empty. Go to Upload Knowledge and add "
            "documents before searching."
        )
        return

    st.write(f"**Documents available to search:** {len(documents)}")

    search_phrase = st.text_input(
        "Enter a keyword or phrase",
        placeholder="e.g., hydraulic pressure, roller vibration, lubrication schedule",
    ).strip()

    if not search_phrase:
        st.info("Enter a keyword or phrase to search the current session collection.")
        return

    matching_documents = find_matching_documents(documents, search_phrase)
    result_count = len(matching_documents)

    if result_count == 1:
        st.success("1 matching document found")
    elif result_count > 1:
        st.success(f"{result_count} matching documents found")
    else:
        st.warning(
            "No matching documents were found. Try another keyword or add more "
            "documents to the collection."
        )
        return

    for match in matching_documents:
        document = match["document"]

        with st.expander(f"{document['file_name']} ({document['category']})", expanded=True):
            st.write(f"**File name:** {document['file_name']}")
            st.write(f"**Category:** {document['category']}")
            st.write("**Relevant snippet:**")
            st.write(match["snippet"])


def show_maintenance_insights_page():
    """Show a neutral overview of the current session document collection."""
    initialize_document_collection()

    st.title("Maintenance Insights")
    st.write(
        "This page summarizes documents currently loaded in the temporary "
        "browser-session collection. It is a collection overview only, not "
        "predictive maintenance, machine diagnosis, or AI analysis."
    )

    documents = st.session_state.get("document_collection", [])

    if not documents:
        st.info(
            "Your current session collection is empty. Go to Upload Knowledge, "
            "add documents to the collection, and then return to this page to "
            "see a simple local overview."
        )
        return

    category_counts = {}
    file_types = set()
    documents_with_text_count = 0

    for document in documents:
        category = document.get("category", "Uncategorized")
        category_counts[category] = category_counts.get(category, 0) + 1
        file_types.add(get_document_file_type(document))

        if has_extracted_text(document):
            documents_with_text_count += 1

    st.subheader("Collection Overview")
    metric_columns = st.columns(4)
    metric_columns[0].metric("Total Documents", len(documents))
    metric_columns[1].metric("Categories Represented", len(category_counts))
    metric_columns[2].metric("File Types Represented", len(file_types))
    metric_columns[3].metric(
        "Documents with Extracted Text Available",
        documents_with_text_count,
    )

    st.subheader("Category Distribution")
    category_chart_data = pd.DataFrame(
        {
            "Category": list(category_counts.keys()),
            "Document Count": list(category_counts.values()),
        }
    ).sort_values("Document Count", ascending=False)

    category_chart = px.bar(
        category_chart_data,
        x="Category",
        y="Document Count",
        title="Document Count by Category",
        text="Document Count",
    )
    category_chart.update_layout(yaxis_title="Document Count", xaxis_title="Category")
    st.plotly_chart(category_chart, use_container_width=True)

    st.subheader("Category Coverage Overview")
    represented_categories = set(category_counts.keys())
    known_represented_categories = [
        category for category in CATEGORIES if category in represented_categories
    ]
    not_represented_categories = [
        category for category in CATEGORIES if category not in represented_categories
    ]

    coverage_columns = st.columns(2)

    with coverage_columns[0]:
        st.markdown("**Currently represented**")
        if known_represented_categories:
            for category in known_represented_categories:
                st.write(f"- {category}")
        else:
            st.write("No standard categories are currently represented.")

    with coverage_columns[1]:
        st.markdown("**Not yet represented**")
        if not_represented_categories:
            for category in not_represented_categories:
                st.write(f"- {category}")
        else:
            st.write("All standard categories are currently represented.")

    st.subheader("Document Inventory")
    filter_options = ["All Categories"] + sorted(category_counts.keys())
    selected_category_filter = st.selectbox("Filter by category", filter_options)

    if selected_category_filter == "All Categories":
        filtered_documents = documents
    else:
        filtered_documents = [
            document
            for document in documents
            if document.get("category", "Uncategorized") == selected_category_filter
        ]

    inventory_rows = build_document_inventory_rows(filtered_documents)
    st.dataframe(
        pd.DataFrame(inventory_rows),
        width="stretch",
        hide_index=True,
    )

    st.info(
        "Limitation note: This overview is based only on temporary in-session "
        "uploaded documents. Refreshing the browser or restarting the app clears "
        "the collection. This page does not perform predictive maintenance, "
        "root-cause analysis, or machine diagnosis."
    )


def show_export_report_page():
    """Show simple CSV exports for the current temporary document collection."""
    initialize_document_collection()

    st.title("Export Report")
    st.write(
        "Download a simple inventory of the documents currently loaded in this "
        "temporary FactoryBrain AI session."
    )

    st.info(
        "This export only reflects documents currently loaded in this browser "
        "session. The collection is temporary and clears after browser refresh or "
        "app restart. This is not a permanent archive."
    )
    st.warning(
        "This is not a formal enterprise, compliance, maintenance, safety, or "
        "audit report. It is not AI analysis, predictive maintenance, or "
        "root-cause analysis."
    )

    documents = st.session_state["document_collection"]

    if not documents:
        st.info(
            "Your current session collection is empty. Go to Upload Knowledge, "
            "add documents to the collection, and then return here to download "
            "a document inventory CSV."
        )
        return

    st.subheader("Export Scope")
    export_scope = st.radio(
        "Choose what to include",
        ["Entire Current Collection", "One Category Only"],
    )

    if export_scope == "One Category Only":
        represented_categories = sorted(
            {document.get("category", "Uncategorized") for document in documents}
        )
        selected_category = st.selectbox(
            "Choose one category to export",
            represented_categories,
        )
        selected_documents = [
            document
            for document in documents
            if document.get("category", "Uncategorized") == selected_category
        ]
        file_suffix = make_safe_filename_part(selected_category)
    else:
        selected_category = "All Categories"
        selected_documents = documents
        file_suffix = "all"

    metrics = calculate_export_summary_metrics(selected_documents)
    inventory_data_frame = build_export_inventory_data_frame(selected_documents)
    summary_data_frame = build_export_summary_data_frame(
        export_scope,
        selected_category,
        metrics,
    )

    st.subheader("Export Summary")
    metric_columns = st.columns(5)
    metric_columns[0].metric("Documents Included", metrics["documents_included"])
    metric_columns[1].metric(
        "Categories Represented",
        metrics["categories_represented"],
    )
    metric_columns[2].metric(
        "File Types Represented",
        metrics["file_types_represented"],
    )
    metric_columns[3].metric(
        "Documents with Extracted Text Available",
        metrics["documents_with_text"],
    )
    metric_columns[4].metric(
        "Documents without Extracted Text Available",
        metrics["documents_without_text"],
    )

    st.markdown("### Category Breakdown")
    st.dataframe(
        build_category_breakdown_data_frame(selected_documents),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Document Inventory Preview")
    st.dataframe(
        inventory_data_frame,
        width="stretch",
        hide_index=True,
    )

    st.download_button(
        "Download Document Inventory CSV",
        data=convert_data_frame_to_safe_csv(inventory_data_frame),
        file_name=f"factorybrain_document_inventory_{file_suffix}.csv",
        mime="text/csv",
    )

    st.download_button(
        "Download Export Summary CSV",
        data=convert_data_frame_to_safe_csv(summary_data_frame),
        file_name=f"factorybrain_export_summary_{file_suffix}.csv",
        mime="text/csv",
    )

    st.info(
        "Limitation note: This is a metadata-based export. Actual extracted "
        "document text and original uploaded file contents are intentionally not "
        "included. The export is temporary-session information only and does not "
        "create a permanent archive, compliance record, audit trail, or "
        "AI-generated report."
    )


def show_guidance_list(items):
    """Show short guidance items as beginner-friendly bullet points."""
    for item in items:
        st.write(f"- {item}")


def show_troubleshooting_guidance(selected_issue, observation_note):
    """Show the predefined rule-based guidance for one selected issue."""
    guidance = TROUBLESHOOTING_GUIDANCE[selected_issue]

    st.success(f"Suggested first checks for: {selected_issue}")

    if observation_note.strip():
        st.info(
            "Your optional note is visible only on this screen during the current "
            "session. It is not analyzed by AI and does not change the guidance."
        )

    st.markdown("### Why this situation needs attention")
    st.write(guidance["attention"])

    st.markdown("### Immediate safe actions")
    show_guidance_list(guidance["safe_actions"])

    st.markdown("### Suggested first checks - only if authorized")
    show_guidance_list(guidance["checks"])

    st.markdown("### Record before escalation")
    show_guidance_list(guidance["record"])

    st.markdown("### Suggested escalation")
    st.write(guidance["escalation"])

    st.markdown("### Suggested Search Factory Brain keywords")
    st.write(", ".join(guidance["keywords"]))
    st.caption(
        "These are only suggested search terms for the Search Factory Brain page. "
        "This assistant does not automatically search documents or claim that "
        "related documents were found."
    )

    st.markdown("### Final safety reminder")
    st.warning(
        "This guidance is a structured first-response aid only. Follow your site "
        "procedures and escalate whenever safety, quality, or equipment reliability "
        "is at risk."
    )


def show_troubleshooting_assistant_page():
    """Show a basic rule-based troubleshooting helper for factory situations."""
    st.title("Troubleshooting Assistant")
    st.write(
        "A basic rule-based first-response helper for common manufacturing "
        "situations, using Cold Rolling Mill examples alongside broader factory "
        "safety, quality, and maintenance scenarios."
    )

    st.warning(
        "Honest limitation and safety note: This page does not diagnose equipment "
        "or determine root causes. Follow site SOPs, lockout/tagout rules, safety "
        "requirements, and authorization procedures. Stop work and escalate "
        "immediately when an unsafe condition exists."
    )
    st.info(
        "This helper uses predefined rules only. It does not read uploaded "
        "documents, search the temporary collection, or perform AI analysis."
    )

    issue_options = list(TROUBLESHOOTING_GUIDANCE.keys())
    selected_issue = st.selectbox(
        "Choose a manufacturing situation",
        issue_options,
        index=None,
        placeholder=TROUBLESHOOTING_PLACEHOLDER,
    )

    observation_note = st.text_area(
        "Additional observable details (optional)",
        placeholder=(
            "Example: timing, machine area, alarm display, coil number, or process condition"
        ),
        max_chars=500,
        height=100,
    )
    st.caption(
        "You can note observations such as timing, machine area, alarm display, "
        "coil number, or process condition. These notes are not analyzed by AI. "
        "The selected issue option, not the typed note, controls the rule-based "
        "guidance. The note is not permanently stored."
    )

    if st.button("Show Suggested First Checks"):
        if selected_issue is None:
            st.warning(
                "Please select a manufacturing situation before showing suggested "
                "first checks."
            )
            return

        st.divider()

        if selected_issue == "Safety, guarding, or unsafe-condition concern":
            st.error(
                "Safety concern selected. Stop work or halt the process where "
                "required by site procedure, keep people clear, and escalate immediately."
            )

        show_troubleshooting_guidance(selected_issue, observation_note)


def show_portfolio_case_study_page():
    """Show the static portfolio explanation page for the prototype."""
    st.title("FactoryBrain AI — Portfolio Case Study")
    st.write(
        "A local-first manufacturing knowledge prototype designed to make "
        "fragmented factory information easier to organize, search, review, "
        "and export."
    )

    st.warning(
        "Honest positioning: FactoryBrain AI is an AI Strategist portfolio "
        "prototype, not a production-ready enterprise platform. It does not "
        "diagnose equipment, replace qualified engineers, make safety decisions, "
        "or currently use real AI reasoning, machine learning, predictive "
        "maintenance, or root-cause analysis."
    )

    st.divider()

    st.subheader("The Problem")
    st.write(
        "Manufacturing knowledge is often spread across many everyday documents. "
        "A small prototype cannot solve every factory knowledge problem, but it "
        "can demonstrate a practical first step: organizing local documents so "
        "teams can find and review basic information more easily."
    )

    problem_columns = st.columns(2)

    with problem_columns[0]:
        st.markdown("**Common knowledge sources**")
        st.write("- SOPs")
        st.write("- Maintenance logs")
        st.write("- Shift reports")
        st.write("- Defect reports")
        st.write("- Safety checklists")
        st.write("- Machine manuals")
        st.write("- Operational notes")

    with problem_columns[1]:
        st.markdown("**Practical difficulty**")
        st.write("- Important information may be scattered across files and folders.")
        st.write(
            "- Teams may spend time searching for the right document during "
            "maintenance, quality, or operational discussions."
        )
        st.write(
            "- Knowledge visibility can be weak when documents are not organized "
            "by type or easy to search."
        )
        st.write(
            "- A first-response workflow may require checking procedures, records, "
            "and escalation paths quickly."
        )

    st.divider()

    st.subheader("Who This Prototype Is Designed For")
    user_columns = st.columns(5)
    intended_users = [
        "Plant managers",
        "Maintenance supervisors",
        "Production engineers",
        "Operations teams",
        "Manufacturing business owners",
    ]

    for column, user_group in zip(user_columns, intended_users):
        with column:
            st.markdown(f"**{user_group}**")

    st.info(
        "This prototype is intended for demonstration and portfolio discussion. "
        "It is not intended for live enterprise deployment in its current form."
    )

    st.divider()

    st.subheader("Current MVP Capabilities")
    capability_columns = st.columns(2)

    with capability_columns[0]:
        st.markdown("**1. Upload and categorize local factory documents**")
        st.write(
            "- Supports TXT, CSV, XLSX, XLS, and text-extractable PDF files."
        )
        st.write(
            "- Documents can be categorized as SOP, Maintenance Log, Shift Report, "
            "Defect Report, Safety Checklist, Machine Manual, or Other."
        )

        st.markdown("**2. Create a temporary in-session document collection**")
        st.write("- Documents remain available only during the current browser session.")
        st.write("- The collection clears on refresh or app restart.")

        st.markdown("**3. Search extracted text locally**")
        st.write(
            "- Supports basic case-insensitive keyword and phrase search within "
            "the temporary collection."
        )
        st.write("- Shows document matches and nearby text snippets.")

    with capability_columns[1]:
        st.markdown("**4. Review collection coverage**")
        st.write(
            "- Shows document totals, represented categories, file types, "
            "extracted-text availability, category coverage, and inventory information."
        )

        st.markdown("**5. Use structured troubleshooting guidance**")
        st.write(
            "- Provides local rule-based first-response guidance for predefined "
            "manufacturing concerns."
        )
        st.write("- Uses safety-oriented and authorization-aware wording.")
        st.write(
            "- Includes realistic Cold Rolling Mill examples alongside broader "
            "manufacturing scenarios."
        )

        st.markdown("**6. Export a document inventory**")
        st.write("- Downloads a full-collection or category-filtered CSV inventory.")
        st.write("- Includes a summary CSV.")
        st.write(
            "- Does not export raw extracted document text or original source files."
        )

    st.divider()

    st.subheader("Example Workflow: Cold Rolling Mill Alignment Concern")
    st.info(
        "This is an example workflow, not an automated maintenance decision system."
    )

    workflow_steps = [
        (
            "A maintenance supervisor or production engineer notices a strip "
            "tracking or alignment concern."
        ),
        (
            "They begin with the Troubleshooting Assistant to review safe "
            "first-response guidance and suggested search terms."
        ),
        (
            "They search the temporary collection for relevant SOPs, maintenance "
            "logs, shift reports, or machine manuals."
        ),
        (
            "They review what information is available and identify missing "
            "document coverage through Maintenance Insights."
        ),
        (
            "They export a category-filtered or full document inventory CSV for "
            "follow-up review, handover, or meeting preparation."
        ),
        (
            "Qualified personnel still follow site procedures, authorization "
            "requirements, escalation processes, and safety controls."
        ),
    ]

    for step_number, workflow_step in enumerate(workflow_steps, start=1):
        st.write(f"{step_number}. {workflow_step}")

    st.divider()

    st.subheader("AI Strategist Approach Demonstrated")
    st.write(
        "This MVP is designed as a portfolio reflection on responsible product "
        "scoping, not as a claim of live factory deployment."
    )
    st.write(
        "- Framed a practical manufacturing knowledge-access problem before "
        "adding advanced AI."
    )
    st.write("- Prioritized a stable, local-first workflow over complex features.")
    st.write(
        "- Designed the product around document organization, simple retrieval, "
        "visibility, and safe operational guidance."
    )
    st.write("- Used clear limitations to avoid overclaiming AI capability.")
    st.write(
        "- Kept potentially high-risk areas, such as safety decisions and "
        "equipment diagnosis, with qualified human personnel."
    )
    st.write(
        "- Built in small, testable stages so each capability could be manually "
        "verified."
    )

    st.divider()

    st.subheader("Current Limitations and Deliberate Boundaries")

    with st.expander("View current limitations and boundaries", expanded=True):
        limitation_columns = st.columns(2)

        with limitation_columns[0]:
            st.write(
                "- Temporary in-session collection only; no permanent database storage"
            )
            st.write(
                "- No user accounts, permissions, authentication, or role-based access"
            )
            st.write(
                "- No real AI reasoning, generative AI, RAG, embeddings, or vector search"
            )
            st.write(
                "- No predictive maintenance, failure prediction, root-cause "
                "detection, or machine-health scoring"
            )
            st.write("- No automatic document interpretation or recommendation engine")

        with limitation_columns[1]:
            st.write("- Basic keyword and phrase search only")
            st.write("- PDF extraction works only for text-extractable PDFs")
            st.write("- CSV and Excel extraction are basic")
            st.write(
                "- Export produces CSV inventory metadata only, not a permanent "
                "archive, compliance report, original files, or full extracted "
                "document text"
            )
            st.write(
                "- The Troubleshooting Assistant provides structured guidance only "
                "and does not replace qualified engineers, site procedures, or "
                "safety controls"
            )

    st.divider()

    st.subheader("Potential Future Roadmap")
    st.write(
        "These are future possibilities for discussion, not current features or promises."
    )

    roadmap_columns = st.columns(3)

    with roadmap_columns[0]:
        st.markdown("**Stage 1: Strengthen the local prototype**")
        st.write("- Improve document validation and extraction feedback")
        st.write("- Improve filtering and search usability")
        st.write("- Expand document inventory and reporting options")
        st.write("- Add more clearly defined rule-based operational scenarios")

    with roadmap_columns[1]:
        st.markdown("**Stage 2: Controlled document retrieval improvements**")
        st.write(
            "- Add durable storage, such as SQLite, only after the session-based "
            "workflow is stable"
        )
        st.write("- Add better document indexing and retrieval")
        st.write(
            "- Explore controlled, cited AI-assisted retrieval with clear "
            "human-review requirements"
        )

    with roadmap_columns[2]:
        st.markdown("**Stage 3: Enterprise-readiness considerations**")
        st.write("- Role-based access")
        st.write("- Document governance")
        st.write("- Audit and approval workflows")
        st.write("- Stronger security and privacy controls")
        st.write("- Integration planning with approved internal factory systems")

    st.info(
        "Any real deployment would require factory-specific process design, "
        "safety review, IT and security review, data governance, and qualified "
        "engineering involvement."
    )

    st.divider()

    st.subheader("What This Portfolio Project Demonstrates")
    demonstration_columns = st.columns(2)

    with demonstration_columns[0]:
        st.write("- Manufacturing problem framing")
        st.write("- Local-first MVP scoping")
        st.write("- Operational workflow design")
        st.write("- Honest AI capability positioning")

    with demonstration_columns[1]:
        st.write("- Safety-aware product thinking")
        st.write("- Document knowledge-management concepts")
        st.write("- User-focused feature prioritization")
        st.write("- Iterative testing and validation")

    st.success(
        "FactoryBrain AI demonstrates how an AI Strategist can begin with a "
        "focused operational problem, build a useful and testable prototype, "
        "and define a responsible path toward more advanced capabilities."
    )


# Set the browser tab title and page layout.
st.set_page_config(
    page_title="FactoryBrain AI",
    page_icon="FB",
    layout="wide",
)


# List of pages shown in the sidebar navigation.
pages = [
    "Home",
    "Upload Knowledge",
    "Search Factory Brain",
    "Maintenance Insights",
    "Troubleshooting Assistant",
    "Export Report",
    "Portfolio Case Study",
]


# Sidebar navigation for the prototype.
st.sidebar.title("FactoryBrain AI")
st.sidebar.caption("Manufacturing knowledge assistant")
selected_page = st.sidebar.radio("Navigation", pages)


if selected_page == "Home":
    # Main landing page content for the portfolio prototype.
    st.title("FactoryBrain AI")
    st.subheader("Manufacturing Company Brain Prototype")

    st.write(
        "Upload and organize local factory documents, search extracted knowledge, "
        "review collection coverage, use structured rule-based troubleshooting "
        "guidance, and export a CSV document inventory."
    )

    st.markdown("## Project Explanation")
    st.write(
        "FactoryBrain AI is a local-first manufacturing knowledge prototype designed "
        "to help teams work with fragmented SOPs, maintenance logs, shift reports, "
        "defect reports, safety checklists, machine manuals, and operational notes. "
        "The current MVP supports document organization, temporary session-based "
        "collection, local keyword search, collection visibility, structured "
        "troubleshooting guidance, and CSV inventory export."
    )

    st.markdown("## Business Problem")
    st.write(
        "Manufacturing companies often keep important operational information across "
        "files, folders, spreadsheets, PDFs, manuals, logs, and informal notes. This "
        "can make it harder to find the right information during operational, "
        "maintenance, quality, or safety discussions."
    )

    st.markdown("## Target Users")
    st.write(
        "The target users are plant managers, maintenance supervisors, production "
        "engineers, operations teams, and manufacturing business owners."
    )

    st.markdown("## Current MVP Status")
    st.write(
        "FactoryBrain AI currently includes local upload support for TXT, CSV, XLSX, "
        "XLS, and text-extractable PDF files; document categorization; a temporary "
        "in-session document collection; basic local keyword and phrase search; a "
        "Maintenance Insights collection overview; rule-based, safety-aware "
        "Troubleshooting Assistant guidance; CSV document inventory and export "
        "summary download; and an in-app Portfolio Case Study page."
    )
    st.write(
        "This prototype is local-only and session-based. It does not currently provide "
        "permanent storage, real AI reasoning, predictive maintenance, root-cause "
        "detection, or enterprise workflow controls."
    )

    st.markdown("## User Workflow")
    st.write(
        "Upload Knowledge -> Search Factory Brain -> Review Maintenance Insights -> "
        "Use Troubleshooting Assistant -> Export Report"
    )

elif selected_page == "Upload Knowledge":
    show_upload_knowledge_page()

elif selected_page == "Search Factory Brain":
    show_search_factory_brain_page()

elif selected_page == "Maintenance Insights":
    show_maintenance_insights_page()

elif selected_page == "Troubleshooting Assistant":
    show_troubleshooting_assistant_page()

elif selected_page == "Export Report":
    show_export_report_page()

elif selected_page == "Portfolio Case Study":
    show_portfolio_case_study_page()
