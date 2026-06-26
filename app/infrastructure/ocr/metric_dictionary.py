from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricSpec:
    code: str
    name: str
    aliases: tuple[str, ...]
    unit: str
    kind: str = "numeric"  # "numeric" | "bp_pair" | "categorical"
    categories: tuple[str, ...] = field(default_factory=tuple)


METRIC_SPECS: list[MetricSpec] = [
    MetricSpec("height", "신장", ("신장",), "cm"),
    MetricSpec("weight", "체중", ("체중",), "kg"),
    MetricSpec("waist", "허리둘레", ("허리둘레",), "cm"),
    MetricSpec("bmi", "체질량지수", ("체질량지수",), "kg/m2"),
    MetricSpec("systolic_bp", "수축기혈압", (), "mmHg"),
    MetricSpec("diastolic_bp", "이완기혈압", (), "mmHg"),
    # 혈압은 한 라벨에서 두 값을 추출하므로 bp_pair 전용 스펙을 둔다.
    MetricSpec("blood_pressure", "혈압", ("혈압",), "mmHg", kind="bp_pair"),
    MetricSpec("fasting_glucose", "공복혈당", ("공복혈당",), "mg/dL"),
    MetricSpec(
        "urine_protein",
        "요단백",
        ("요단백", "단백"),
        "",
        kind="categorical",
        categories=("음성", "약양성", "양성"),
    ),
    MetricSpec("creatinine", "혈청크레아티닌", ("혈청크레아티닌", "크레아티닌"), "mg/dL"),
    MetricSpec("egfr", "신사구체여과율", ("신사구체여과율", "GFR", "eGFR"), "mL/min"),
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
    return s.replace(" ", "").replace("\t", "")


def find_spec_by_label(token: str) -> MetricSpec | None:
    norm = normalize_label(token)
    if not norm:
        return None
    for spec in METRIC_SPECS:
        for alias in spec.aliases:
            if normalize_label(alias) in norm:
                return spec
    return None
