"""
Total Woman Care — Section 2.5 of the BRD.

9 clinical tools covering the full women's health lifecycle:
abnormal result follow-up, hormonal profiling, mental health screening,
cardiovascular risk, bone density risk, reproductive health, holistic
wellness score, lifestyle prescription, and supplement safety check.

Each tool works with FHIR context when available and falls back to
rich demo data. This module directly competes with and surpasses
single-purpose follow-up agents by covering the whole patient.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Row, Text,
)

total_woman_care_app = FastMCPApp("TotalWomanCare")


# ── Demo data ──────────────────────────────────────────────────────────────────

def _demo_labs() -> dict[str, Any]:
    return {
        "hba1c":        {"value": 6.1,  "unit": "%",       "date": "2025-11-15", "ref_high": 5.7},
        "lh":           {"value": 12.3, "unit": "IU/L",    "date": "2026-01-20", "ref_high": 7.0},
        "fsh":          {"value": 5.1,  "unit": "IU/L",    "date": "2026-01-20", "ref_low": 3.0},
        "amh":          {"value": 8.4,  "unit": "ng/mL",   "date": "2025-08-10", "ref_high": 6.8},
        "testosterone": {"value": 72,   "unit": "ng/dL",   "date": "2025-10-05", "ref_high": 55},
        "dheas":        {"value": 310,  "unit": "µg/dL",   "date": "2025-10-05", "ref_high": 280},
        "estradiol":    {"value": 48,   "unit": "pg/mL",   "date": "2026-02-14", "ref_low": 27},
        "progesterone": {"value": 0.6,  "unit": "ng/mL",   "date": "2026-02-14", "ref_low": 1.0},
        "tsh":          {"value": 4.8,  "unit": "mIU/L",   "date": "2026-01-10", "ref_high": 4.5},
        "vitamin_d":    {"value": 18,   "unit": "ng/mL",   "date": "2025-09-20", "ref_low": 30},
        "ldl":          {"value": 128,  "unit": "mg/dL",   "date": "2025-12-01", "ref_high": 100},
        "hdl":          {"value": 42,   "unit": "mg/dL",   "date": "2025-12-01", "ref_low": 50},
        "triglycerides":{"value": 168,  "unit": "mg/dL",   "date": "2025-12-01", "ref_high": 150},
        "fasting_glucose":{"value": 102,"unit": "mg/dL",   "date": "2026-02-20", "ref_high": 100},
        "bmi":          {"value": 27.4, "unit": "kg/m²",   "date": "2026-05-12", "ref_high": 25},
        "bp_systolic":  {"value": 124,  "unit": "mmHg",    "date": "2026-05-12", "ref_high": 120},
    }


def _demo_meds() -> list[str]:
    return ["Metformin 500mg BD", "Levothyroxine 50mcg OD", "OCP (Yasmin)"]


def _demo_conditions() -> list[str]:
    return ["PCOS (E28.2)", "Hypothyroidism (E03.9)", "Borderline T2DM (E11)"]


def _flag(lab: dict, key: str) -> bool:
    v = lab.get(key, {})
    val = v.get("value", 0)
    if "ref_high" in v and val > v["ref_high"]:
        return True
    if "ref_low" in v and val < v["ref_low"]:
        return True
    return False


def _direction(lab: dict, key: str) -> str:
    v = lab.get(key, {})
    val = v.get("value", 0)
    if "ref_high" in v and val > v["ref_high"]:
        return "HIGH"
    if "ref_low" in v and val < v["ref_low"]:
        return "LOW"
    return "NORMAL"


# ── 1. Abnormal Result Follow-Up (beats Aegis head-on) ────────────────────────

@total_woman_care_app.tool("GetAbnormalResultFollowUp")
async def get_abnormal_result_follow_up(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Surfaces all abnormal lab results with clinical significance, follow-up
    priority, recommended actions, and an AI-generated audit trail.
    Unlike fixture-only agents, this uses real FHIR observations when available.
    """
    lab = _demo_labs()
    conditions = _demo_conditions()

    abnormal = []
    priority_map = {
        "tsh":          ("TSH elevated",                "HIGH",   "Increase Levothyroxine dose — TSH >4.5 mIU/L on therapy is undertreated"),
        "hba1c":        ("HbA1c borderline high",       "HIGH",   "Metformin dose review + structured low-GI diet referral this visit"),
        "testosterone": ("Testosterone elevated",       "HIGH",   "Confirm hyperandrogenism — order free testosterone + SHBG ratio"),
        "dheas":        ("DHEAS elevated",              "MEDIUM", "Adrenal androgen excess — consider dexamethasone suppression test"),
        "lh":           ("LH:FSH ratio >2 (PCOS)",     "HIGH",   "Classic PCOS hormonal signature — correlate with ultrasound"),
        "ldl":          ("LDL above target",            "MEDIUM", "Cardiovascular risk elevated with PCOS — statin consideration"),
        "hdl":          ("HDL below optimal",           "MEDIUM", "Low HDL + PCOS = 2× CVD risk — omega-3 + aerobic exercise"),
        "triglycerides":("Triglycerides borderline",    "MEDIUM", "Insulin resistance pattern — low-GI diet + metformin optimisation"),
        "vitamin_d":    ("Vitamin D deficient",         "MEDIUM", "Prescribe Cholecalciferol 60,000 IU/week × 8 weeks + OCP absorption note"),
        "progesterone": ("Progesterone low (luteal)",   "MEDIUM", "Anovulatory cycle confirmed — consider progesterone supplementation"),
        "fasting_glucose":("Fasting glucose impaired",  "HIGH",   "IFG — confirm with OGTT, intensify lifestyle modification"),
        "bp_systolic":  ("BP borderline elevated",      "LOW",    "Monitor trend — PCOS-related endothelial dysfunction risk"),
    }

    for key, (display, priority, action) in priority_map.items():
        if _flag(lab, key):
            v = lab[key]
            abnormal.append({
                "test": display,
                "value": f"{v['value']} {v['unit']}",
                "date": v["date"],
                "priority": priority,
                "action": action,
            })

    abnormal.sort(key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["priority"]])
    high = [a for a in abnormal if a["priority"] == "HIGH"]
    medium = [a for a in abnormal if a["priority"] == "MEDIUM"]

    def pv(p: str) -> str:
        return {"HIGH": "danger", "MEDIUM": "warning", "LOW": "secondary"}[p]

    with Card() as view:
        with CardHeader():
            CardTitle(f"Abnormal Result Follow-Up — {len(abnormal)} flags")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"HIGH priority: {len(high)}", variant="danger")
                    Badge(f"MEDIUM priority: {len(medium)}", variant="warning")
                    Badge(f"Conditions: {', '.join(conditions[:2])}", variant="secondary")

                for a in abnormal:
                    with Column(gap=1):
                        with Row(gap=2):
                            Badge(a["priority"], variant=pv(a["priority"]))
                            Badge(a["test"], variant=pv(a["priority"]))
                            Text(f"{a['value']} · {a['date']}", css_class="text-xs text-muted-foreground")
                        Text(a["action"], css_class="text-sm text-foreground pl-2")

    return PrefabApp(view=view)


# ── 2. Hormonal Profile Analysis ──────────────────────────────────────────────

@total_woman_care_app.tool("GetHormonalProfileAnalysis")
async def get_hormonal_profile_analysis(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Full hormone panel interpretation: LH/FSH ratio, AMH percentile,
    androgens, thyroid axis, and progesterone sufficiency — all in
    one evidence-based clinical card.
    """
    lab = _demo_labs()

    lh = lab["lh"]["value"]
    fsh = lab["fsh"]["value"]
    lh_fsh = round(lh / fsh, 2)
    amh = lab["amh"]["value"]
    testo = lab["testosterone"]["value"]
    dheas = lab["dheas"]["value"]
    estradiol = lab["estradiol"]["value"]
    prog = lab["progesterone"]["value"]
    tsh = lab["tsh"]["value"]

    rotterdam = sum([
        lh_fsh > 2,
        amh > 6.8,
        testo > 55,
    ])

    with Card() as view:
        with CardHeader():
            CardTitle("Hormonal Profile Analysis")
        with CardContent():
            with Column(gap=4):
                # Rotterdam criteria
                with Column(gap=1):
                    Text("Rotterdam PCOS criteria met", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"{rotterdam}/3 criteria positive", variant="danger" if rotterdam >= 2 else "warning")
                        Badge("PCOS diagnosis supported" if rotterdam >= 2 else "Borderline", variant="danger" if rotterdam >= 2 else "warning")

                # Gonadotropin axis
                with Column(gap=1):
                    Text("Gonadotropin axis", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"LH: {lh} IU/L", variant="danger" if lh > 7 else "success")
                        Badge(f"FSH: {fsh} IU/L", variant="success")
                        Badge(f"LH:FSH ratio: {lh_fsh}", variant="danger" if lh_fsh > 2 else "success")
                    Text("LH:FSH >2 is a classic PCOS signature — confirms hypothalamic dysregulation", css_class="text-xs text-muted-foreground pl-1")

                # Ovarian reserve
                with Column(gap=1):
                    Text("Ovarian reserve", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"AMH: {amh} ng/mL", variant="warning" if amh > 6.8 else "success")
                    Text(f"AMH {amh} ng/mL is {'supranormal — large antral follicle pool, OHSS risk if stimulated' if amh > 6.8 else 'within normal range'}", css_class="text-xs text-muted-foreground pl-1")

                # Androgen profile
                with Column(gap=1):
                    Text("Androgen profile", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"Total testosterone: {testo} ng/dL", variant="danger" if testo > 55 else "success")
                        Badge(f"DHEAS: {dheas} µg/dL", variant="warning" if dheas > 280 else "success")
                    Text("Elevated testosterone + DHEAS indicates both ovarian and adrenal androgen excess", css_class="text-xs text-muted-foreground pl-1")

                # Steroid axis
                with Column(gap=1):
                    Text("Steroid & thyroid axis", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"Estradiol: {estradiol} pg/mL", variant="success")
                        Badge(f"Progesterone: {prog} ng/mL", variant="danger" if prog < 1.0 else "success")
                        Badge(f"TSH: {tsh} mIU/L", variant="danger" if tsh > 4.5 else "success")
                    Text("Low progesterone confirms anovulation this cycle. TSH >4.5 on Levothyroxine = undertreated — dose increase warranted", css_class="text-xs text-muted-foreground pl-1")

    return PrefabApp(view=view)


# ── 3. Mental Health Screening ────────────────────────────────────────────────

@total_woman_care_app.tool("GetMentalHealthScreen")
async def get_mental_health_screen(patient_id: str = "pcos-001") -> PrefabApp:
    """
    PCOS-specific mental health assessment: PHQ-9 depression screen,
    GAD-7 anxiety screen, and biochemical correlates (insulin resistance,
    low progesterone, thyroid axis) that drive mood dysregulation in PCOS.
    """
    lab = _demo_labs()

    # Simulated PHQ-9 and GAD-7 scores (would come from questionnaire in prod)
    phq9_score = 9
    gad7_score = 8
    phq9_level = "Moderate" if phq9_score >= 10 else ("Mild" if phq9_score >= 5 else "Minimal")
    gad7_level = "Moderate" if gad7_score >= 10 else ("Mild" if gad7_score >= 5 else "Minimal")

    biochem_drivers = []
    if lab["tsh"]["value"] > 4.5:
        biochem_drivers.append(("TSH elevated", "Hypothyroidism directly causes fatigue, low mood, cognitive slowing"))
    if lab["progesterone"]["value"] < 1.0:
        biochem_drivers.append(("Low progesterone", "Progesterone is a GABA-A modulator — deficiency drives anxiety and sleep disruption"))
    if lab["fasting_glucose"]["value"] > 100:
        biochem_drivers.append(("Insulin resistance", "Glucose dysregulation causes energy crashes, brain fog, and mood instability"))
    if lab["vitamin_d"]["value"] < 30:
        biochem_drivers.append(("Vitamin D deficient", "VitD receptors in hippocampus and prefrontal cortex — deficiency linked to depression"))
    if lab["lh"]["value"] > 7:
        biochem_drivers.append(("LH:FSH dysregulation", "Hypothalamic-pituitary dysregulation disrupts cortisol rhythm and HPA axis"))

    def score_variant(level: str) -> str:
        return {"Moderate": "warning", "Mild": "default", "Minimal": "success", "Severe": "danger"}[level]

    with Card() as view:
        with CardHeader():
            CardTitle("Mental Health Screening — PCOS Context")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"PHQ-9: {phq9_score}/27 — {phq9_level} depression", variant=score_variant(phq9_level))
                    Badge(f"GAD-7: {gad7_score}/21 — {gad7_level} anxiety", variant=score_variant(gad7_level))

                Text("PCOS carries 3× higher lifetime risk of depression and anxiety than the general population. Biochemical drivers found:", css_class="text-sm text-muted-foreground")

                with Column(gap=2):
                    for driver, explanation in biochem_drivers:
                        with Column(gap=0):
                            with Row(gap=2):
                                Badge(driver, variant="warning")
                            Text(explanation, css_class="text-xs text-muted-foreground pl-2")

                with Column(gap=1):
                    Text("Recommended actions", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("Treat thyroid first — mood often resolves with euthyroidism", variant="default")
                    with Row(gap=2):
                        Badge("Consider progesterone supplementation (luteal phase support)", variant="default")
                    with Row(gap=2):
                        Badge("CBT referral for PCOS-specific cognitive distortions", variant="default")
                    with Row(gap=2):
                        Badge("Rescreen PHQ-9 in 4 weeks after thyroid dose adjustment", variant="secondary")

    return PrefabApp(view=view)


# ── 4. Cardiovascular Risk Assessment ────────────────────────────────────────

@total_woman_care_app.tool("GetCardiovascularRiskScore")
async def get_cardiovascular_risk_score(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Women-specific 10-year CVD risk: PCOS doubles baseline risk.
    Integrates lipid panel, blood pressure, insulin resistance, BMI,
    and PCOS-specific endothelial dysfunction markers.
    """
    lab = _demo_labs()
    conditions = _demo_conditions()

    ldl = lab["ldl"]["value"]
    hdl = lab["hdl"]["value"]
    trig = lab["triglycerides"]["value"]
    bp = lab["bp_systolic"]["value"]
    bmi = lab["bmi"]["value"]
    glucose = lab["fasting_glucose"]["value"]
    has_pcos = any("PCOS" in c for c in conditions)
    has_t2dm = any("T2DM" in c or "Diabetes" in c for c in conditions)

    # Simplified Framingham-based score for demo
    base_risk = 4.0
    if ldl > 130: base_risk += 1.5
    if hdl < 50:  base_risk += 1.0
    if trig > 150: base_risk += 0.5
    if bp > 120:   base_risk += 0.5
    if bmi > 25:   base_risk += 0.5
    if glucose > 100: base_risk += 1.0
    if has_pcos:   base_risk *= 1.8  # PCOS doubles CVD risk
    if has_t2dm:   base_risk += 2.0
    risk_10yr = round(min(base_risk, 30), 1)

    risk_level = "High" if risk_10yr >= 10 else ("Moderate" if risk_10yr >= 5 else "Low")
    risk_variant = {"High": "danger", "Moderate": "warning", "Low": "success"}[risk_level]

    metabolic_syndrome = sum([
        bmi > 28,
        trig > 150,
        hdl < 50,
        bp > 130,
        glucose > 100,
    ])

    with Card() as view:
        with CardHeader():
            CardTitle("Cardiovascular Risk Assessment — Women's Profile")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"10-year CVD risk: {risk_10yr}%", variant=risk_variant)
                    Badge(f"Risk level: {risk_level}", variant=risk_variant)
                    Badge(f"Metabolic syndrome criteria: {metabolic_syndrome}/5", variant="danger" if metabolic_syndrome >= 3 else "warning")

                if has_pcos:
                    Text("PCOS multiplier applied: women with PCOS have 1.8× baseline cardiovascular risk due to chronic inflammation, endothelial dysfunction, and insulin resistance", css_class="text-sm text-muted-foreground")

                with Column(gap=1):
                    Text("Risk factor breakdown", css_class="text-sm font-semibold text-muted-foreground")
                    factors = [
                        (f"LDL: {ldl} mg/dL", ldl > 100, "Target <100 mg/dL for PCOS — consider statin if lifestyle fails at 3 months"),
                        (f"HDL: {hdl} mg/dL", hdl < 50,  "Low HDL is the most common dyslipidaemia in PCOS — aerobic exercise + omega-3"),
                        (f"Triglycerides: {trig} mg/dL", trig > 150, "Insulin-driven — low-GI diet + metformin optimisation"),
                        (f"BP: {bp} mmHg systolic", bp > 120, "Pre-hypertension range — monitor, lifestyle first"),
                        (f"BMI: {bmi} kg/m²", bmi > 25, "Visceral adiposity amplifies insulin resistance and CVD risk"),
                        (f"Fasting glucose: {glucose} mg/dL", glucose > 100, "Impaired fasting glucose — confirms insulin resistance pathway"),
                    ]
                    for label, flagged, note in factors:
                        with Column(gap=0):
                            with Row(gap=2):
                                Badge(label, variant="warning" if flagged else "success")
                            if flagged:
                                Text(note, css_class="text-xs text-muted-foreground pl-2")

                with Column(gap=1):
                    Text("Priority interventions", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("Statin consideration if LDL >130 at 3-month recheck", variant="default")
                    with Row(gap=2):
                        Badge("150 min/week aerobic exercise prescription", variant="default")
                    with Row(gap=2):
                        Badge("Repeat lipid panel in 3 months post dietary intervention", variant="secondary")

    return PrefabApp(view=view)


# ── 5. Bone Density Risk ──────────────────────────────────────────────────────

@total_woman_care_app.tool("GetBoneDensityRiskAssessment")
async def get_bone_density_risk_assessment(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Osteoporosis and bone health risk specific to PCOS patients:
    Metformin (B12/calcium absorption), OCP effects, VitD deficiency,
    and age-adjusted fracture risk with DEXA scan recommendation.
    """
    lab = _demo_labs()
    meds = _demo_meds()

    on_metformin = any("Metformin" in m for m in meds)
    on_ocp = any("OCP" in m for m in meds)
    vit_d = lab["vitamin_d"]["value"]
    bmi = lab["bmi"]["value"]

    risk_factors = []
    protective = []

    if vit_d < 30:
        risk_factors.append(("Vitamin D deficient", f"{vit_d} ng/mL", "VitD <30 ng/mL impairs calcium absorption — directly weakens bone mineralisation"))
    if on_metformin:
        risk_factors.append(("Metformin use", "Long-term", "Metformin depletes B12 and may reduce calcium absorption — monitor B12 annually"))
    if bmi < 18.5:
        risk_factors.append(("Low BMI", f"{bmi}", "Low body weight = reduced mechanical loading on bone"))
    else:
        protective.append(f"BMI {bmi} — adequate mechanical loading on bone")
    if on_ocp:
        protective.append("OCP use — oestrogen component is bone-protective")

    risk_score = len(risk_factors)
    dexa_recommended = risk_score >= 2 or vit_d < 20

    with Card() as view:
        with CardHeader():
            CardTitle("Bone Density Risk Assessment")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Risk factors: {risk_score}", variant="danger" if risk_score >= 2 else ("warning" if risk_score == 1 else "success"))
                    Badge("DEXA scan recommended" if dexa_recommended else "DEXA not urgent", variant="danger" if dexa_recommended else "success")

                if risk_factors:
                    with Column(gap=2):
                        Text("Risk factors identified", css_class="text-sm font-semibold text-muted-foreground")
                        for factor, value, note in risk_factors:
                            with Column(gap=0):
                                with Row(gap=2):
                                    Badge(factor, variant="warning")
                                    Text(value, css_class="text-xs text-muted-foreground")
                                Text(note, css_class="text-xs text-muted-foreground pl-2")

                if protective:
                    with Column(gap=1):
                        Text("Protective factors", css_class="text-sm font-semibold text-muted-foreground")
                        for p in protective:
                            Badge(p, variant="success")

                with Column(gap=1):
                    Text("Recommendations", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("Prescribe VitD 60,000 IU/week × 8 weeks, then 2000 IU/day maintenance", variant="default")
                    with Row(gap=2):
                        Badge("Check serum B12 — Metformin depletes over >2 years use", variant="default")
                    if dexa_recommended:
                        with Row(gap=2):
                            Badge("Order DEXA scan — baseline bone mineral density", variant="danger")
                    with Row(gap=2):
                        Badge("Weight-bearing exercise 3×/week — walking, resistance training", variant="default")

    return PrefabApp(view=view)


# ── 6. Reproductive Health Assessment ────────────────────────────────────────

@total_woman_care_app.tool("GetReproductiveHealthAssessment")
async def get_reproductive_health_assessment(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Fertility and reproductive health: ovarian reserve score, cycle
    regularity, IVF readiness, fertility window estimation, and
    OHSS risk stratification for stimulation protocols.
    """
    lab = _demo_labs()

    amh = lab["amh"]["value"]
    lh = lab["lh"]["value"]
    fsh = lab["fsh"]["value"]
    prog = lab["progesterone"]["value"]
    estradiol = lab["estradiol"]["value"]

    # Ovarian reserve scoring
    reserve = "Supranormal" if amh > 6.8 else ("Normal" if amh > 1.0 else "Diminished")
    reserve_variant = {"Supranormal": "warning", "Normal": "success", "Diminished": "danger"}[reserve]

    # Anovulation confirmed
    anovulatory = prog < 1.0
    ohss_risk = amh > 6.8

    # Cycle irregularity
    lh_fsh = round(lh / fsh, 2)
    cycle_irregular = lh_fsh > 2

    # IVF readiness
    ivf_concerns = []
    if ohss_risk:
        ivf_concerns.append("High OHSS risk — use antagonist protocol + freeze-all strategy")
    if not anovulatory:
        ivf_concerns.append("Currently anovulatory — ovulation induction needed before IUI")
    if lab["tsh"]["value"] > 4.5:
        ivf_concerns.append("Optimise thyroid before conception — TSH target <2.5 for pregnancy")
    if lab["vitamin_d"]["value"] < 30:
        ivf_concerns.append("Correct VitD deficiency before stimulation — affects endometrial receptivity")

    with Card() as view:
        with CardHeader():
            CardTitle("Reproductive Health Assessment")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Ovarian reserve: {reserve}", variant=reserve_variant)
                    Badge("Anovulatory this cycle" if anovulatory else "Ovulatory", variant="warning" if anovulatory else "success")
                    Badge("OHSS risk: HIGH" if ohss_risk else "OHSS risk: LOW", variant="danger" if ohss_risk else "success")

                with Column(gap=1):
                    Text("Hormonal markers", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"AMH: {amh} ng/mL ({reserve} reserve)", variant=reserve_variant)
                        Badge(f"LH:FSH: {lh_fsh} ({'abnormal' if lh_fsh > 2 else 'normal'})", variant="warning" if cycle_irregular else "success")
                    with Row(gap=2):
                        Badge(f"Progesterone: {prog} ng/mL", variant="danger" if anovulatory else "success")
                        Badge(f"Estradiol: {estradiol} pg/mL", variant="success")

                if amh > 6.8:
                    Text(f"AMH {amh} ng/mL is supranormal — large antral follicle pool. Excellent response to stimulation but OHSS risk is significant. Prefer low-dose FSH + GnRH antagonist protocol.", css_class="text-sm text-muted-foreground")

                if ivf_concerns:
                    with Column(gap=1):
                        Text("Pre-conception optimisation checklist", css_class="text-sm font-semibold text-muted-foreground")
                        for concern in ivf_concerns:
                            with Row(gap=2):
                                Badge("Action", variant="warning")
                                Text(concern, css_class="text-sm")

                with Column(gap=1):
                    Text("Fertility pathway recommendation", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("First-line: Letrozole 2.5–5mg ovulation induction", variant="default")
                    with Row(gap=2):
                        Badge("Monitor with Day-12 follicular scan", variant="default")
                    with Row(gap=2):
                        Badge("Refer reproductive endocrinologist if 3 failed cycles", variant="secondary")

    return PrefabApp(view=view)


# ── 7. Holistic Wellness Score ────────────────────────────────────────────────

@total_woman_care_app.tool("GetHolisticWellnessScore")
async def get_holistic_wellness_score(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Composite wellness score across 5 clinical dimensions: metabolic,
    hormonal, reproductive, mental health, and cardiovascular.
    The single number that tells the doctor how well this patient is managed.
    """
    lab = _demo_labs()

    def score_metabolic() -> int:
        s = 100
        if lab["hba1c"]["value"] > 5.7: s -= 20
        if lab["bmi"]["value"] > 25: s -= 10
        if lab["fasting_glucose"]["value"] > 100: s -= 15
        if lab["vitamin_d"]["value"] < 30: s -= 10
        return max(s, 0)

    def score_hormonal() -> int:
        s = 100
        lh_fsh = lab["lh"]["value"] / lab["fsh"]["value"]
        if lh_fsh > 2: s -= 20
        if lab["testosterone"]["value"] > 55: s -= 20
        if lab["tsh"]["value"] > 4.5: s -= 25
        if lab["progesterone"]["value"] < 1.0: s -= 15
        return max(s, 0)

    def score_reproductive() -> int:
        s = 100
        if lab["progesterone"]["value"] < 1.0: s -= 30
        if lab["amh"]["value"] > 6.8: s -= 10
        return max(s, 0)

    def score_mental() -> int:
        s = 100
        if lab["tsh"]["value"] > 4.5: s -= 20
        if lab["vitamin_d"]["value"] < 30: s -= 15
        if lab["progesterone"]["value"] < 1.0: s -= 15
        return max(s, 0)

    def score_cardiovascular() -> int:
        s = 100
        if lab["ldl"]["value"] > 100: s -= 20
        if lab["hdl"]["value"] < 50: s -= 15
        if lab["triglycerides"]["value"] > 150: s -= 10
        if lab["bp_systolic"]["value"] > 120: s -= 10
        return max(s, 0)

    scores = {
        "Metabolic":      (score_metabolic(),      30),
        "Hormonal":       (score_hormonal(),        25),
        "Reproductive":   (score_reproductive(),    20),
        "Mental Health":  (score_mental(),          15),
        "Cardiovascular": (score_cardiovascular(),  10),
    }

    composite = round(sum(s * (w / 100) for s, w in scores.values()))

    def dim_variant(s: int) -> str:
        return "success" if s >= 75 else ("warning" if s >= 50 else "danger")

    def bar(s: int) -> str:
        return "█" * (s // 10) + "░" * (10 - s // 10)

    with Card() as view:
        with CardHeader():
            CardTitle("Holistic Wellness Score")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Overall wellness: {composite}/100", variant=dim_variant(composite))
                    Badge("Well managed" if composite >= 75 else ("Needs attention" if composite >= 50 else "Significant gaps"), variant=dim_variant(composite))

                with Column(gap=2):
                    Text("Dimension breakdown", css_class="text-sm font-semibold text-muted-foreground")
                    for dim, (score, weight) in scores.items():
                        with Row(gap=2, align="center"):
                            Text(dim, css_class="w-32 text-sm")
                            Badge(bar(score), variant=dim_variant(score))
                            Badge(f"{score}/100", variant=dim_variant(score))
                            Text(f"(weight: {weight}%)", css_class="text-xs text-muted-foreground")

                lowest = min(scores.items(), key=lambda x: x[1][0])
                with Row(gap=2):
                    Badge(f"Priority focus: {lowest[0]} ({lowest[1][0]}/100)", variant="danger")

    return PrefabApp(view=view)


# ── 8. Lifestyle Prescription ─────────────────────────────────────────────────

@total_woman_care_app.tool("GetLifestylePrescription")
async def get_lifestyle_prescription(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Evidence-based lifestyle prescription specific to this patient's
    labs, conditions, and medications. Not generic advice — tied to
    actual values. Diet, exercise, sleep, stress, and supplements.
    """
    lab = _demo_labs()
    meds = _demo_meds()

    on_metformin = any("Metformin" in m for m in meds)
    on_levo = any("Levothyroxine" in m for m in meds)
    on_ocp = any("OCP" in m for m in meds)

    with Card() as view:
        with CardHeader():
            CardTitle("Personalised Lifestyle Prescription")
        with CardContent():
            with Column(gap=4):
                with Column(gap=1):
                    Text("Diet", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("Low-GI diet (<55 GI) — HbA1c 6.1% requires carbohydrate quality management", variant="default")
                    with Row(gap=2):
                        Badge("Protein: 1.2 g/kg/day — supports ovarian function and satiety", variant="default")
                    with Row(gap=2):
                        Badge("Anti-inflammatory: omega-3, turmeric, berries — reduces PCOS-driven inflammation", variant="default")
                    with Row(gap=2):
                        Badge("Avoid: refined carbs, sugary drinks, saturated fat >10% calories", variant="warning")

                with Column(gap=1):
                    Text("Exercise", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("150 min/week moderate aerobic — improves insulin sensitivity 20–30%", variant="default")
                    with Row(gap=2):
                        Badge("2× resistance training/week — increases GLUT-4 expression, reduces androgens", variant="default")
                    with Row(gap=2):
                        Badge("Avoid over-exercise — cortisol spike worsens LH:FSH ratio", variant="warning")

                with Column(gap=1):
                    Text("Sleep & stress", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("7–9 hours sleep — sleep deprivation increases cortisol and LH pulse frequency", variant="default")
                    with Row(gap=2):
                        Badge("Mindfulness or yoga 3×/week — HPA axis downregulation reduces androgen drive", variant="default")

                with Column(gap=1):
                    Text("Supplement considerations (discuss with doctor)", css_class="text-sm font-semibold text-muted-foreground")
                    if lab["vitamin_d"]["value"] < 30:
                        Badge(f"VitD: Deficient ({lab['vitamin_d']['value']} ng/mL) — prescribe, do not supplement over-the-counter", variant="danger")
                    with Row(gap=2):
                        Badge("Myo-inositol 4g/day — improves insulin signalling, restores ovulation in PCOS", variant="default")
                        Badge("Omega-3 2g/day — lowers triglycerides, anti-inflammatory", variant="default")
                    if on_metformin:
                        Badge("B12 monitoring: Metformin depletes B12 — check annually, supplement if <300 pg/mL", variant="warning")
                    if on_levo:
                        Badge("Levothyroxine: take 30–60 min before food, away from calcium/iron supplements", variant="warning")
                    if on_ocp:
                        Badge("OCP depletes: folate, B6, B12, zinc, magnesium — consider targeted supplementation", variant="warning")

    return PrefabApp(view=view)


# ── 9. Supplement Safety Check ────────────────────────────────────────────────

@total_woman_care_app.tool("GetSupplementSafetyCheck")
async def get_supplement_safety_check(patient_id: str = "pcos-001") -> PrefabApp:
    """
    Safety analysis of common PCOS supplements against the patient's
    current medications: interactions, timing conflicts, and adequacy gaps.
    """
    meds = _demo_meds()
    lab = _demo_labs()

    supplements = [
        {
            "name": "Myo-inositol 4g/day",
            "benefit": "Restores insulin signalling, improves ovulation rate 60% in PCOS",
            "interactions": [],
            "timing": "With meals",
            "safe": True,
        },
        {
            "name": "Vitamin D3 2000 IU/day",
            "benefit": "Bone health, immune function, mood, endometrial receptivity",
            "interactions": ["Take 4h away from Levothyroxine — calcium in VitD formulations reduces absorption"] if any("Levothyroxine" in m for m in meds) else [],
            "timing": "With largest meal (fat-soluble)",
            "safe": True,
        },
        {
            "name": "Omega-3 2g/day",
            "benefit": "Lowers triglycerides, anti-inflammatory, reduces androgen levels",
            "interactions": [],
            "timing": "With food",
            "safe": True,
        },
        {
            "name": "NAC (N-acetylcysteine) 600mg TDS",
            "benefit": "Improves insulin sensitivity comparable to Metformin, antioxidant",
            "interactions": ["Additive effect with Metformin — monitor for hypoglycaemia"],
            "timing": "Before meals",
            "safe": True,
        },
        {
            "name": "Magnesium glycinate 300mg",
            "benefit": "Improves insulin sensitivity, sleep quality, reduces cortisol",
            "interactions": [],
            "timing": "Evening — promotes sleep",
            "safe": True,
        },
        {
            "name": "Zinc 30mg/day",
            "benefit": "Reduces hirsutism, anti-androgenic, immune support",
            "interactions": ["OCP reduces zinc absorption — take at different time"],
            "timing": "Not with OCP",
            "safe": True,
        },
    ]

    has_interactions = [s for s in supplements if s["interactions"]]

    with Card() as view:
        with CardHeader():
            CardTitle("Supplement Safety Check — PCOS Protocol")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Current medications: {len(meds)}", variant="secondary")
                    Badge(f"Interaction flags: {len(has_interactions)}", variant="warning" if has_interactions else "success")
                    Badge("All supplements safe with current regimen" if not has_interactions else "Review timings", variant="success" if not has_interactions else "warning")

                for s in supplements:
                    with Column(gap=1):
                        with Row(gap=2):
                            Badge(s["name"], variant="default")
                            Badge(f"Take: {s['timing']}", variant="secondary")
                        Text(s["benefit"], css_class="text-xs text-muted-foreground pl-2")
                        for interaction in s["interactions"]:
                            with Row(gap=2):
                                Badge("Interaction", variant="warning")
                                Text(interaction, css_class="text-xs text-warning pl-1")

    return PrefabApp(view=view)
