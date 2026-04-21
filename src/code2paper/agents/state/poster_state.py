"""poster state management"""

from typing import Dict, Any, Optional, List, Tuple, TypedDict
from dataclasses import dataclass, field
import time


@dataclass
class ModelConfig:
    model_name: str
    provider: str
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class TokenUsage:
    input_text: int = 0
    output_text: int = 0
    input_vision: int = 0
    output_vision: int = 0

    def add_text(self, inp: int, out: int):
        self.input_text += inp
        self.output_text += out

    def add_vision(self, inp: int, out: int):
        self.input_vision += inp
        self.output_vision += out


@dataclass
class APICall:
    agent: str
    call_type: str
    input_tokens: int
    output_tokens: int
    timestamp: float


@dataclass
class TimingMetrics:
    pipeline_start: float = 0.0
    pipeline_end: float = 0.0
    parser_time: float = 0.0
    curator_time: float = 0.0
    layout_optimizer_time: float = 0.0
    color_agent_time: float = 0.0
    font_agent_time: float = 0.0
    title_designer_time: float = 0.0
    renderer_time: float = 0.0
    refine_loop_time: float = 0.0
    validator_time: float = 0.0
    api_calls: List[APICall] = field(default_factory=list)

    def add_api_call(self, agent: str, call_type: str, input_tokens: int, output_tokens: int):
        self.api_calls.append(APICall(
            agent=agent,
            call_type=call_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            timestamp=time.time()
        ))

    def get_total_time(self) -> float:
        if self.pipeline_start == 0.0 or self.pipeline_end == 0.0:
            return 0.0
        return round(self.pipeline_end - self.pipeline_start, 2)

    def get_api_call_count(self) -> int:
        return len(self.api_calls)

    def get_component_percentage(self, component_time: float) -> float:
        total = self.get_total_time()
        if total == 0:
            return 0.0
        return round((component_time / total) * 100, 2)


class PosterState(TypedDict):
    # core paths
    pdf_path: str
    output_dir: str
    poster_name: str

    # model configs
    text_model: ModelConfig
    vision_model: ModelConfig
    ref_image_model: Optional[str]
    ref_image_provider: Optional[str]
    method_overview_ref_image: Optional[str]
    method_overview_style_reference_image: Optional[str]
    method_overview_slide_width: Optional[float]
    method_overview_slide_height: Optional[float]

    # processing results
    images: Optional[Dict[str, Any]]
    tables: Optional[Dict[str, Any]]
    narrative: Optional[Dict[str, str]]
    poster_plan: Optional[List[Dict[str, Any]]]
    poster_width: int
    poster_height: int
    wireframe_layout: Optional[List[Dict[str, Any]]]
    content_filled_layout: Optional[List[Dict[str, Any]]]
    final_layout: Optional[List[Dict[str, Any]]]

    narrative_content: Optional[Dict[str, Any]]
    classified_visuals: Optional[Dict[str, Any]]
    structured_sections: Optional[Dict[str, Any]]
    paper_objects: Optional[Dict[str, Any]]
    tables_structured: Optional[Dict[str, Any]]
    abstract_fulltext: Optional[Dict[str, Any]]
    intro_related_conclusion_summary: Optional[Dict[str, Any]]
    method_experiment_structured_summary: Optional[Dict[str, Any]]
    validation_report: Optional[Dict[str, Any]]
    diagram_spec: Optional[Dict[str, Any]]
    diagram_layout: Optional[Dict[str, Any]]
    entity_links: Optional[Dict[str, Any]]
    validator_report: Optional[Dict[str, Any]]
    task_mode: Optional[str]
    repo_path: Optional[str]
    files_path_list: Optional[List[str]]
    manual_snippets: Optional[Any]
    enable_code_intake_llm_review: Optional[bool]
    code_sources: Optional[Dict[str, Any]]
    core_snippets: Optional[Dict[str, Any]]
    code_intake_report: Optional[Dict[str, Any]]
    method_code_alignment: Optional[Dict[str, Any]]
    dynamic_roles: Optional[List[str]]
    config: Optional[Dict[str, Any]]
    enable_code_analyzer_llm: Optional[bool]
    code_facts: Optional[Dict[str, Any]]
    code_ir: Optional[Dict[str, Any]]
    slide_plan: Optional[Dict[str, Any]]
    layout_plan: Optional[Dict[str, Any]]
    layout_diagnostics: Optional[Dict[str, Any]]
    render_spec: Optional[Dict[str, Any]]
    render_preview_path: Optional[str]
    reuse_intermediates: Optional[bool]
    force_regen_intermediates: Optional[bool]
    enable_refine_llm: Optional[bool]
    max_refine_rounds: Optional[int]
    method_overview_geometry_failed: Optional[bool]
    method_overview_geometry_report: Optional[Dict[str, Any]]
    story_board: Optional[Dict[str, Any]]
    curated_content: Optional[Dict[str, Any]]
    design_layout: Optional[List[Dict[str, Any]]]
    section_title_design: Optional[Dict[str, Any]]
    color_scheme: Optional[Dict[str, str]]
    keywords: Optional[Dict[str, Any]]
    styled_layout: Optional[List[Dict[str, Any]]]

    # poster assets
    url: str
    logo_path: str
    aff_logo_path: Optional[str]

    # metadata
    tokens: TokenUsage
    timing_metrics: TimingMetrics
    current_agent: str
    errors: List[str]


def create_state(pdf_path: str, text_model: str = "gpt-4.1-2025-04-14", vision_model: str = "gpt-4.1-2025-04-14", width: int = 84, height: int = 42, url: str = "", logo_path: str = "", aff_logo_path: str = "", poster_name: Optional[str] = None, output_dir: Optional[str] = None, text_provider: Optional[str] = None, vision_provider: Optional[str] = None) -> PosterState:
    """create initial poster state"""
    from pathlib import Path

    resolved_poster_name = poster_name or (Path(pdf_path).parent.name or "test_poster")
    resolved_output_dir = output_dir or f"output/{resolved_poster_name}"

    return PosterState(
        pdf_path=pdf_path,
        output_dir=resolved_output_dir,
        poster_name=resolved_poster_name,
        text_model=_get_model_config(text_model, provider=text_provider),
        vision_model=_get_model_config(vision_model, provider=vision_provider),
        ref_image_model=None,
        ref_image_provider=None,
        method_overview_ref_image=None,
        method_overview_style_reference_image=None,
        method_overview_slide_width=None,
        method_overview_slide_height=None,
        images=None,
        tables=None,
        narrative=None,
        poster_plan=None,
        poster_width=width,
        poster_height=height,
        wireframe_layout=None,
        content_filled_layout=None,
        final_layout=None,
        narrative_content=None,
        classified_visuals=None,
        structured_sections=None,
        paper_objects=None,
        tables_structured=None,
        abstract_fulltext=None,
        intro_related_conclusion_summary=None,
        method_experiment_structured_summary=None,
        validation_report=None,
        diagram_spec=None,
        diagram_layout=None,
        entity_links=None,
        validator_report=None,
        task_mode=None,
        repo_path=None,
        files_path_list=None,
        manual_snippets=None,
        enable_code_intake_llm_review=None,
        code_sources=None,
        core_snippets=None,
        code_intake_report=None,
        method_code_alignment=None,
        dynamic_roles=None,
        config=None,
        enable_code_analyzer_llm=None,
        code_facts=None,
        code_ir=None,
        slide_plan=None,
        layout_plan=None,
        layout_diagnostics=None,
        render_spec=None,
        render_preview_path=None,
        reuse_intermediates=None,
        force_regen_intermediates=None,
        enable_refine_llm=None,
        max_refine_rounds=None,
        method_overview_geometry_failed=False,
        method_overview_geometry_report=None,
        story_board=None,
        curated_content=None,
        design_layout=None,
        section_title_design=None,
        color_scheme=None,
        keywords=None,
        styled_layout=None,
        url=url,
        logo_path=logo_path,
        aff_logo_path=aff_logo_path,
        tokens=TokenUsage(),
        timing_metrics=TimingMetrics(),
        current_agent="init",
        errors=[]
    )


def _get_model_config(model_id: str, provider: Optional[str] = None) -> ModelConfig:
    """get model configuration"""
    if provider:
        return ModelConfig(model_id, provider)
    if ":" in model_id:
        maybe_provider, maybe_model = model_id.split(":", 1)
        if maybe_provider and maybe_model:
            return ModelConfig(maybe_model, maybe_provider)
    configs = {
        "claude": ModelConfig("claude-sonnet-4-20250514", "anthropic"),
        "claude-sonnet-4-20250514": ModelConfig("claude-sonnet-4-20250514", "anthropic"),
        "claude-opus-4.5": ModelConfig("claude-opus-4-5-20251101", "anthropic"),
        "claude-opus-4-5-20251101": ModelConfig("claude-opus-4-5-20251101", "anthropic"),
        "gemini": ModelConfig("gemini-2.5-pro", "google"),
        "gemini-2.5-pro": ModelConfig("gemini-2.5-pro", "google"),
        "gemini-3-flash-preview-free": ModelConfig("gemini-3-flash-preview-free", "google"),
        "gemini-3.1-flash-image-preview": ModelConfig("gemini-3.1-flash-image-preview", "google"),
        "gemini-3.1-flash-image-preview-free": ModelConfig("gemini-3.1-flash-image-preview-free", "google"),
        "gemini-3-pro-image-preview": ModelConfig("gemini-3-pro-image-preview", "google"),
        "gpt-4o-2024-08-06": ModelConfig("gpt-4o-2024-08-06", "openai"),
        "gpt-4.1-2025-04-14": ModelConfig("gpt-4.1-2025-04-14", "openai"),
        "gpt-4.1-mini-2025-04-14": ModelConfig("gpt-4.1-mini-2025-04-14", "openai"),
        "glm-4.6": ModelConfig("glm-4.6", "zhipu"),
        "glm-4.6v": ModelConfig("glm-4.6v", "zhipu"),
        "glm-4.5": ModelConfig("glm-4.5", "zhipu"),
        "glm-4.5-air": ModelConfig("glm-4.5-air", "zhipu"),
        "glm-4.5v": ModelConfig("glm-4.5v", "zhipu"),
        "glm-4": ModelConfig("glm-4", "zhipu"),
        "glm-4v": ModelConfig("glm-4v", "zhipu"),
        "kimi-k2-turbo-preview": ModelConfig("kimi-k2-turbo-preview", "moonshot"),
        "kimi-k2.5": ModelConfig("kimi-k2.5", "moonshot"),
        "kimi-k2.5-vision": ModelConfig("kimi-k2.5", "moonshot"),
        "moonshot-v1-8k-vision-preview": ModelConfig("moonshot-v1-8k-vision-preview", "moonshot"),
        "Pro/moonshotai/Kimi-K2.5": ModelConfig("Pro/moonshotai/Kimi-K2.5", "moonshot"),
        "MiniMax-M2": ModelConfig("MiniMax-M2", "Minimax"),
        "qwen3-max": ModelConfig("qwen3-max", "Alibaba"),
        "qwen3-vl-plus": ModelConfig("qwen3-vl-plus", "Alibaba"),
        "Qwen/Qwen3.5-397B-A17B": ModelConfig("Qwen/Qwen3.5-397B-A17B", "Alibaba"),
    }
    return configs.get(model_id, configs["gpt-4.1-2025-04-14"])
