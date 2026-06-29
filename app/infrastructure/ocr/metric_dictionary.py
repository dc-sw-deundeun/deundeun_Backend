from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricSpec:
    code: str
    name: str
    aliases: tuple[str, ...]
    unit: str
    kind: str = "numeric"  # "numeric" | "bp_pair" | "hw_pair" | "categorical"
    categories: tuple[str, ...] = field(default_factory=tuple)
    plausible_min: float | None = None
    plausible_max: float | None = None


METRIC_SPECS: list[MetricSpec] = [
    MetricSpec(
        "height",
        "신장",
        ("신장", "키"),
        "cm",
        kind="hw_pair",
        plausible_min=50.0,
        plausible_max=230.0,
    ),
    MetricSpec("weight", "체중", ("체중", "몸무게"), "kg", plausible_min=10.0, plausible_max=300.0),
    MetricSpec("waist", "허리둘레", ("허리둘레",), "cm", plausible_min=30.0, plausible_max=200.0),
    MetricSpec(
        "bmi", "체질량지수", ("체질량지수",), "kg/m2", plausible_min=10.0, plausible_max=70.0
    ),
    MetricSpec("systolic_bp", "수축기혈압", (), "mmHg", plausible_min=60.0, plausible_max=270.0),
    MetricSpec("diastolic_bp", "이완기혈압", (), "mmHg", plausible_min=20.0, plausible_max=160.0),
    MetricSpec("blood_pressure", "혈압", ("혈압", "고혈압", "혈압(최고"), "mmHg", kind="bp_pair"),
    MetricSpec(
        "fasting_glucose",
        "공복혈당",
        ("공복혈당",),
        "mg/dL",
        plausible_min=40.0,
        plausible_max=600.0,
    ),
    MetricSpec(
        "urine_protein",
        "요단백",
        ("요단백",),
        "",
        kind="categorical",
        categories=("음성", "약양성", "양성"),
    ),
    MetricSpec(
        "creatinine",
        "혈청크레아티닌",
        ("혈청크레아티닌", "크레아티닌"),
        "mg/dL",
        plausible_min=0.1,
        plausible_max=30.0,
    ),
    MetricSpec(
        "egfr",
        "신사구체여과율",
        ("신사구체여과율", "GFR", "EGFR"),
        "mL/min",
        plausible_min=0.5,
        plausible_max=200.0,
    ),
    MetricSpec("hemoglobin", "혈색소", ("혈색소",), "g/dL", plausible_min=2.0, plausible_max=25.0),
    MetricSpec("ast", "AST", ("AST", "SGOT"), "U/L", plausible_min=1.0, plausible_max=3000.0),
    MetricSpec("alt", "ALT", ("ALT", "SGPT"), "U/L", plausible_min=1.0, plausible_max=3000.0),
    MetricSpec(
        "gamma_gtp",
        "감마지티피",
        ("감마지티피", "GTP"),
        "U/L",
        plausible_min=1.0,
        plausible_max=3000.0,
    ),
    MetricSpec(
        "total_cholesterol",
        "총콜레스테롤",
        ("총콜레스테롤",),
        "mg/dL",
        plausible_min=50.0,
        plausible_max=700.0,
    ),
    MetricSpec(
        "hdl",
        "HDL콜레스테롤",
        ("HDL콜레스테롤", "HDL"),
        "mg/dL",
        plausible_min=5.0,
        plausible_max=200.0,
    ),
    MetricSpec(
        "ldl",
        "LDL콜레스테롤",
        ("LDL콜레스테롤", "LDL"),
        "mg/dL",
        plausible_min=10.0,
        plausible_max=500.0,
    ),
    MetricSpec(
        "triglyceride",
        "트리글리세라이드",
        ("트리글리세라이드", "중성지방"),
        "mg/dL",
        plausible_min=10.0,
        plausible_max=5000.0,
    ),
]


METRIC_SPEC_BY_CODE: dict[str, MetricSpec] = {spec.code: spec for spec in METRIC_SPECS}


def normalize_label(s: str) -> str:
    return s.replace(" ", "").replace("\t", "").replace("-", "").upper()


def _strip_unit_suffix(text: str) -> str:
    """'허리둘레(cm)' → '허리둘레' 처럼 괄호 단위 접미사를 제거한다."""
    idx = text.find("(")
    return text[:idx].strip() if idx > 0 else text


def _is_close_enough(alias: str, text: str, max_typos: int) -> bool:
    if len(alias) != len(text):
        return False
    return sum(a != b for a, b in zip(alias, text)) <= max_typos


def find_best_alias_match(text: str, max_typos: int = 2) -> tuple[MetricSpec, str] | None:
    """정규화된 text에서 가장 긴 alias를 가진 스펙을 반환한다.

    - alias 길이 ≤ 3: exact match (신장, 키, LDL, HDL 등 단어 충돌 방지)
    - alias 길이 ≥ 4: substring match 또는 ≤max_typos자 OCR 오인식 허용
    - 괄호 단위 접미사('(cm)', '(mg/dL)' 등)를 제거한 후에도 재시도
    alias 길이가 같으면 METRIC_SPECS 순서상 앞선 스펙이 우선한다.
    max_typos=2: 단일 토큰 OCR 오인식 허용 (기본값).
    max_typos=1: 멀티토큰 조인 시 — "허리키둘"(2자 오차)이 "허리둘레"에 오매칭하는 것을 방지.
    max_typos=0: substring match만 허용.
    """
    norm = normalize_label(text)
    if not norm:
        return None
    norm_stripped = normalize_label(_strip_unit_suffix(text))
    best_spec: MetricSpec | None = None
    best_alias: str = ""
    best_exact: bool = False  # True = substring match, False = typo-only match
    for spec in METRIC_SPECS:
        for alias in spec.aliases:
            norm_alias = normalize_label(alias)
            if len(norm_alias) <= 3:
                matched = norm_alias == norm or norm_alias == norm_stripped
                is_exact = matched
            else:
                # alias가 토큰 결합 텍스트의 앞에 있어야 진짜 라벨 위치.
                # 중간/끝에 alias가 나오면 별개 라벨의 문자가 포함된 오매칭.
                # 선행 괄호 허용: "(LDL-콜레스테롤)" → 괄호 제거 후 매칭.
                is_exact = any(
                    c.startswith(norm_alias) or c.lstrip("([{（").startswith(norm_alias)
                    for c in (norm, norm_stripped)
                )
                is_typo = not is_exact and any(
                    _is_close_enough(norm_alias, candidate, max_typos=max_typos)
                    for candidate in (norm, norm_stripped)
                )
                matched = is_exact or is_typo
            alias_len = len(norm_alias)
            # 더 긴 alias 우선. 같은 길이면 exact(substring) > typo 우선.
            if matched and (
                alias_len > len(best_alias)
                or (alias_len == len(best_alias) and is_exact and not best_exact)
            ):
                best_spec = spec
                best_alias = norm_alias
                best_exact = is_exact
    return (best_spec, best_alias) if best_spec else None


def is_plausible(spec: MetricSpec, value: str) -> bool:
    if spec.plausible_min is None and spec.plausible_max is None:
        return True
    try:
        v = float(value)
    except (ValueError, TypeError):
        return True
    if spec.plausible_min is not None and v < spec.plausible_min:
        return False
    if spec.plausible_max is not None and v > spec.plausible_max:
        return False
    return True
