"""Study labels, statistical groups and Extended Data aliases."""
CENTRES = ("Main centre", "Centre I", "Centre II", "Centre III", "Centre IV")
EXTERNAL_N = {"Centre I": 14, "Centre II": 21, "Centre III": 14, "Centre IV": 25}
METRICS = ("DSC", "HD95", "ASD")
TARGETS = ("GTVp", "CTV1", "CTV2", "GTVn")
SMALL = ("Optic chiasm", "Cochlea", "Eustachian tube bone", "Internal auditory canal",
         "Lens", "Optic nerve", "Pituitary", "Temporomandibular joint", "Tympanic cavity",
         "Vestibule/semicircular canals")
LARGE = ("Eye", "Glottic larynx", "Supraglottic larynx", "Mandible", "Oral cavity",
         "Parotid gland", "Brain stem", "Thyroid", "Temporal lobe", "Submandibular gland", "Spinal cord")
GROUPS = {"Small OARs": SMALL, "Large OARs": LARGE}
GROUP_LABELS = {"Small OARs": "Small OARs (≤ 4 cm³)", "Large OARs": "Large OARs (> 4 cm³)"}
ENDPOINTS = (*GROUP_LABELS.values(), *TARGETS)
S6_ORDER = ("GTVp", "GTVn", "CTV1", "CTV2", *GROUP_LABELS.values(), *SMALL, *LARGE)
S6_LABELS = {GROUP_LABELS['Small OARs']: 'Small-OAR composite',
             GROUP_LABELS['Large OARs']: 'Large-OAR composite'}
STRATEGIES = ("Image-only baseline", "Direct DIR propagation", "PCG-UNet")
TIMES = ("Algorithm-processing time (s)", "Review-and-modification interval (s)", "Derived combined time (s)")
CASE_ORDER = (
    ("Central nervous", "Brain stem"), ("Central nervous", "Spinal cord"),
    ("Central nervous", "Eye"), ("Central nervous", "Temporal lobe"),
    ("Visual", "Optic chiasm"), ("Visual", "Lens"), ("Visual", "Pituitary"), ("Visual", "Optic nerve"),
    ("Auditory", "Cochlea"), ("Auditory", "Eustachian tube bone"),
    ("Auditory", "Internal auditory canal"), ("Auditory", "Tympanic cavity"),
    ("Auditory", "Vestibule/semicircular canals"),
    ("Oral", "Parotid gland"), ("Oral", "Temporomandibular joint"), ("Oral", "Oral cavity"),
    ("Oral", "Submandibular gland"), ("Oral", "Mandible"),
    ("Pharyngo-laryngeal", "Supraglottic larynx"), ("Pharyngo-laryngeal", "Thyroid"),
    ("Pharyngo-laryngeal", "Glottic larynx"),
)
FIGURES = ('5','6','ED4','ED5','ED6','ED7')
ALIASES = {'S4':'ED4','S5':'ED5','S6':'ED6','S7':'ED7'}
def models(centre):
    if centre not in CENTRES: raise ValueError(f'Unknown centre: {centre}')
    return (("Conventional U-Net comparator", "Locked source model") if centre == "Main centre"
            else ("Pre-adaptation model", "Locally adapted model"))
def expected_n(centre, roi):
    return (12 if roi in ("GTVp", "GTVn") else 29) if centre == "Main centre" else EXTERNAL_N[centre]
def roi_group(roi):
    return next((g for g, members in GROUPS.items() if roi in members),
                next((g for g, label in GROUP_LABELS.items() if roi == label), 'Targets'))
def unit(metric):
    if metric not in METRICS: raise ValueError(f'Unknown metric: {metric}')
    return 'unitless' if metric == 'DSC' else 'mm'
