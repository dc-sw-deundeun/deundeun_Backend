from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricSpec:
    code: str
    name: str
    aliases: tuple[str, ...]
    unit: str
    kind: str = "numeric"  # "numeric" | "bp_pair" | "hw_pair" | "categorical"
    categories: tuple[str, ...] = field(default_factory=tuple)


METRIC_SPECS: list[MetricSpec] = [
    MetricSpec("height", "신장", ("신장", "키"), "cm", kind="hw_pair"),
    MetricSpec("weight", "체중", ("체중",), "kg"),
    MetricSpec("waist", "허리둘레", ("허리둘레",), "cm"),
    MetricSpec("bmi", "체질량지수", ("체질량지수",), "kg/m2"),
    MetricSpec("systolic_bp", "수축기혈압", (), "mmHg"),
    MetricSpec("diastolic_bp", "이완기혈압", (), "mmHg"),
    MetricSpec("blood_pressure", "혈압", ("혈압",), "mmHg", kind="bp_pair"),
    MetricSpec("fasting_glucose", "공복혈당", ("공복혈당",), "mg/dL"),
    MetricSpec(
        "urine_protein",
        "요단백",
        ("요단백",),
        "",
        kind="categorical",
        categories=("음성", "약양성", "양성"),
    ),
    MetricSpec("creatinine", "혈청크레아티닌", ("혈청크레아티닌", "크레아티닌"), "mg/dL"),
    MetricSpec("egfr", "신사구체여과율", ("신사구체여과율", "GFR", "EGFR"), "mL/min"),
    MetricSpec("hemoglobin", "혈색소", ("혈색소",), "g/dL"),
    MetricSpec("ast", "AST", ("AST", "SGOT"), "U/L"),
    MetricSpec("alt", "ALT", ("ALT", "SGPT"), "U/L"),
    MetricSpec("gamma_gtp", "감마지티피", ("감마지티피", "GTP"), "U/L"),
    MetricSpec("total_cholesterol", "총콜레스테롤", ("총콜레스테롤",), "mg/dL"),
    MetricSpec("hdl", "HDL콜레스테롤", ("HDL",), "mg/dL"),
    MetricSpec("ldl", "LDL콜레스테롤", ("LDL",), "mg/dL"),
    MetricSpec("triglyceride", "트리글리세라이드", ("트리글리세라이드", "중성지방"), "mg/dL"),
]


def normalize_label(s: str) -> str:
    return s.replace(" ", "").replace("\t", "").upper()


def find_best_alias_match(text: str) -> tuple[MetricSpec, str] | None:
    """정규화된 text에서 가장 긴 alias를 가진 스펙을 반환한다.

    - alias 길이 ≤ 3: exact match (신장, 키, LDL, HDL 등 단어 충돌 방지)
    - alias 길이 ≥ 4: substring match (크레아티닌(mg/dL) 등 부가 정보 포함 토큰 대응)
    alias 길이가 같으면 METRIC_SPECS 순서상 앞선 스펙이 우선한다.
    """
    norm = normalize_label(text)
    if not norm:
        return None
    best_spec: MetricSpec | None = None
    best_alias: str = ""
    for spec in METRIC_SPECS:
        for alias in spec.aliases:
            norm_alias = normalize_label(alias)
            if len(norm_alias) <= 3:
                matched = norm_alias == norm
            else:
                matched = norm_alias in norm
            if matched and len(norm_alias) > len(best_alias):
                best_spec = spec
                best_alias = norm_alias
    return (best_spec, best_alias) if best_spec else None
