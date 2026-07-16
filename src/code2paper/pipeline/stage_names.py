"""Canonical product stage names for the Code2Paper pipeline."""

STAGE_SPECS = [
    ("01", "input_resolution", "Prepare input", "01_input"),
    ("02", "intake", "Understand code", "02_intake"),
    ("03", "analysis", "Analyze structure", "03_analysis"),
    ("04", "evidence", "Build method evidence", "04_evidence"),
    ("05", "grounding", "Ground equations and symbols", "05_grounding"),
    ("06", "authoring", "Write method", "06_authoring"),
    ("07", "validation", "Validate method", "07_validation"),
    ("08", "rendering", "Render outputs", "08_rendering"),
    ("09", "finalize", "Finalize package", "09_finalize"),
]

STAGES = [(name, title) for _number, name, title, _artifact_dir in STAGE_SPECS]

STAGE_ARTIFACT_DIRS = {
    name: artifact_dir for _number, name, _title, artifact_dir in STAGE_SPECS
}

RUN_ARTIFACT_DIR = "10_run"
