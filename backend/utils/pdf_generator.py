"""
Sovereign V5 - Professional Compliance Report Generator
Generates enterprise-grade PDF reports matching reference format
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, HRFlowable, KeepTogether
)
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, Circle, String
from reportlab.graphics.charts.piecharts import Pie
from datetime import datetime
from io import BytesIO


# ============================================
# HELPER FUNCTIONS
# ============================================
def parse_severity(severity_value):
    """Convert severity to integer, handling both numeric and text formats"""
    if severity_value is None:
        return 0
    if isinstance(severity_value, (int, float)):
        return int(severity_value)
    if isinstance(severity_value, str):
        severity_map = {
            'CRITICAL': 9,
            'HIGH': 7,
            'MEDIUM': 5,
            'MAJOR': 7,
            'MINOR': 3,
            'LOW': 2
        }
        # Try to get from map first
        upper_val = severity_value.upper().strip()
        if upper_val in severity_map:
            return severity_map[upper_val]
        # Try to parse as number
        try:
            return int(severity_value)
        except ValueError:
            return 5  # Default to medium
    return 5


def get_violation_field(violation, *keys, default='N/A'):
    """Try multiple field names and return first match"""
    for key in keys:
        value = violation.get(key)
        if value and value != 'N/A' and str(value).strip():
            return value
    return default


def format_confidence(confidence):
    """Convert confidence to percentage (0.92 -> 92)"""
    if confidence is None:
        return 95  # Default
    try:
        conf_float = float(confidence)
        # If <= 1, it's in 0-1 range (0.92), convert to percentage
        if conf_float <= 1:
            return int(conf_float * 100)
        # Already a percentage (92)
        return int(conf_float)
    except (ValueError, TypeError):
        return 95  # Default


def get_specific_business_impact(violation):
    """Get specific business impact based on severity and framework"""
    # Check if already has specific impact (not generic)
    existing = violation.get('business_impact', '')
    if existing and existing != 'Impact assessment required' and len(existing) > 30:
        return existing

    severity = violation.get('severity', '').upper()
    framework = violation.get('framework', '').upper()

    # CRITICAL violations - specific high-value impacts
    if severity == 'CRITICAL':
        if 'GDPR' in framework:
            return 'Up to €20M or 4% of annual global turnover. Immediate regulatory action likely. Public disclosure required. Data processing suspension risk.'
        elif 'EU' in framework or 'AI' in framework:
            return 'Up to €35M or 7% of annual global turnover. Product ban possible. Mandatory notification to authorities. Market access restrictions.'
        elif 'SOX' in framework:
            return 'SEC enforcement action. Officer criminal liability (5-20 years prison). Trading suspension risk. Investor class-action lawsuits. Restatement of financials.'
        else:
            return 'Severe regulatory penalties. Operational shutdown risk. Executive personal liability. License revocation possible.'

    # MAJOR violations
    elif severity == 'MAJOR' or severity == 'HIGH':
        if 'GDPR' in framework:
            return 'Up to €10M or 2% of annual global turnover. Data protection authority investigation. Corrective action orders. Processing restrictions.'
        elif 'EU' in framework or 'AI' in framework:
            return 'Up to €15M or 3% of annual global turnover. Product restrictions possible. Enhanced monitoring requirements. Compliance audits.'
        elif 'SOX' in framework:
            return 'SEC investigation. Material weakness disclosure required. Restatement requirements. Stock price impact. Enhanced regulatory scrutiny.'
        else:
            return 'Significant regulatory penalties. Compliance review required. Corrective action orders. Reputational damage.'

    # MINOR/LOW violations
    elif severity in ['MINOR', 'LOW', 'MEDIUM']:
        return 'Regulatory warning. Corrective action required within 30-90 days. Limited financial exposure. Enhanced monitoring.'

    # Default fallback
    return 'Compliance review recommended. Risk mitigation advised. Regulatory attention possible.'


def preprocess_violations(violations):
    """
    Preprocess violations to fix common issues:
    1. Article 5 (EU AI Act Prohibited Practices) always CRITICAL
    2. Format confidence to percentage
    3. Add specific business impact
    4. Normalize severity labels
    """
    processed = []

    for v in violations:
        # Make a copy to avoid modifying original
        v_copy = v.copy()

        # Fix 1: Article 5 override - ALWAYS CRITICAL
        article = str(v_copy.get('article_violated', '')).lower()
        framework = str(v_copy.get('framework', '')).lower()

        if ('article 5' in article or 'article5' in article) and ('eu' in framework or 'ai' in framework):
            v_copy['severity'] = 'CRITICAL'
            v_copy['priority'] = 'P0'
            v_copy['timeline'] = 'Immediate (0-14 days)'
            print(f"DEBUG: Overriding Article 5 to CRITICAL: {article}")

        # Fix 2: Add specific business impact if missing or generic
        if not v_copy.get('business_impact') or v_copy.get('business_impact') == 'Impact assessment required':
            v_copy['business_impact'] = get_specific_business_impact(v_copy)

        # Fix 3: Normalize confidence (done in format_confidence function)

        processed.append(v_copy)

    # Deduplicate by article (keep highest confidence)
    unique_violations = {}
    for v in processed:
        article = v.get('article_violated', 'Unknown')
        framework = v.get('framework', 'Unknown')
        key = f"{framework}-{article.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')}"

        conf = v.get('confidence', 0)
        if key not in unique_violations or conf > unique_violations[key].get('confidence', 0):
            unique_violations[key] = v

    return list(unique_violations.values())


# ============================================
# COLOR PALETTE
# ============================================
COLORS = {
    'primary': colors.HexColor('#0f172a'),      # Dark navy
    'secondary': colors.HexColor('#1e293b'),    # Slate
    'accent': colors.HexColor('#3b82f6'),       # Blue
    'critical': colors.HexColor('#dc2626'),     # Red
    'critical_bg': colors.HexColor('#fef2f2'),  # Light red
    'high': colors.HexColor('#f97316'),         # Orange
    'high_bg': colors.HexColor('#fff7ed'),      # Light orange
    'medium': colors.HexColor('#eab308'),       # Yellow
    'medium_bg': colors.HexColor('#fefce8'),    # Light yellow
    'low': colors.HexColor('#22c55e'),          # Green
    'low_bg': colors.HexColor('#f0fdf4'),       # Light green
    'text': colors.HexColor('#1e293b'),         # Dark text
    'text_muted': colors.HexColor('#64748b'),   # Muted text
    'border': colors.HexColor('#e2e8f0'),       # Light border
    'white': colors.white,
}

# ============================================
# CUSTOM STYLES
# ============================================
def get_custom_styles():
    styles = getSampleStyleSheet()

    # Cover title
    styles.add(ParagraphStyle(
        name='CoverTitle',
        parent=styles['Title'],
        fontSize=28,
        textColor=COLORS['primary'],
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    ))

    # Cover subtitle
    styles.add(ParagraphStyle(
        name='CoverSubtitle',
        parent=styles['Normal'],
        fontSize=14,
        textColor=COLORS['text_muted'],
        alignment=TA_CENTER,
        spaceAfter=8
    ))

    # Section heading
    styles.add(ParagraphStyle(
        name='SectionHeading',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=COLORS['primary'],
        spaceBefore=20,
        spaceAfter=12,
        fontName='Helvetica-Bold'
    ))

    # Subsection heading
    styles.add(ParagraphStyle(
        name='SubsectionHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=COLORS['primary'],
        spaceBefore=16,
        spaceAfter=8,
        fontName='Helvetica-Bold'
    ))

    # Body text - modify existing style
    styles['BodyText'].fontSize = 10
    styles['BodyText'].textColor = COLORS['text']
    styles['BodyText'].spaceAfter = 8
    styles['BodyText'].leading = 14
    styles['BodyText'].alignment = TA_JUSTIFY

    # Violation title
    styles.add(ParagraphStyle(
        name='ViolationTitle',
        parent=styles['Heading2'],
        fontSize=13,
        textColor=COLORS['primary'],
        spaceBefore=4,
        spaceAfter=12,
        fontName='Helvetica-Bold',
        leading=16
    ))

    # Label style
    styles.add(ParagraphStyle(
        name='Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=COLORS['text_muted'],
        fontName='Helvetica-Bold'
    ))

    # Value style
    styles.add(ParagraphStyle(
        name='Value',
        parent=styles['Normal'],
        fontSize=10,
        textColor=COLORS['text'],
    ))

    # Footer
    styles.add(ParagraphStyle(
        name='Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=COLORS['text_muted'],
        alignment=TA_CENTER
    ))

    return styles


# ============================================
# HELPER FUNCTIONS
# ============================================
def get_severity_color(severity):
    """Return color based on severity level (expects numeric 1-10)"""
    severity = parse_severity(severity)

    if severity >= 8:
        return COLORS['critical'], COLORS['critical_bg'], 'CRITICAL'
    elif severity >= 6:
        return COLORS['high'], COLORS['high_bg'], 'HIGH'
    elif severity >= 4:
        return COLORS['medium'], COLORS['medium_bg'], 'MEDIUM'
    else:
        return COLORS['low'], COLORS['low_bg'], 'LOW'


def get_priority_label(severity):
    """Return priority label based on severity (expects numeric 1-10)"""
    severity = parse_severity(severity)

    if severity >= 8:
        return 'P0', 'Immediate (0-14 days)'
    elif severity >= 6:
        return 'P1', 'Short-term (15-30 days)'
    else:
        return 'P2', 'Medium-term (30-90 days)'


def create_severity_badge(severity_text, color):
    """Create a colored severity badge"""
    return f'<font color="{color.hexval()}">{severity_text}</font>'


# ============================================
# PAGE TEMPLATES
# ============================================
class ReportTemplate:
    """Custom page template with header/footer"""

    def __init__(self, doc, assessment_id):
        self.doc = doc
        self.assessment_id = assessment_id

    def on_page(self, canvas, doc):
        """Draw header and footer on each page"""
        canvas.saveState()

        # Header line
        canvas.setStrokeColor(COLORS['border'])
        canvas.setLineWidth(0.5)
        canvas.line(50, letter[1] - 50, letter[0] - 50, letter[1] - 50)

        # Header text
        canvas.setFont('Helvetica-Bold', 9)
        canvas.setFillColor(COLORS['primary'])
        canvas.drawString(50, letter[1] - 40, "SOVEREIGN")

        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(COLORS['text_muted'])
        canvas.drawRightString(letter[0] - 50, letter[1] - 40, f"Assessment ID: {self.assessment_id[:20]}...")

        # Footer line
        canvas.line(50, 50, letter[0] - 50, 50)

        # Footer text
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(COLORS['text_muted'])
        canvas.drawString(50, 35, "CONFIDENTIAL - This report contains sensitive compliance information")
        canvas.drawRightString(letter[0] - 50, 35, f"Page {doc.page}")

        canvas.restoreState()


# ============================================
# REPORT SECTIONS
# ============================================
def create_cover_page(styles, data):
    """Generate cover page elements"""
    elements = []

    # Add spacing from top
    elements.append(Spacer(1, 1.5*inch))

    # Logo placeholder (SOVEREIGN text)
    elements.append(Paragraph("SOVEREIGN", styles['CoverTitle']))
    elements.append(Paragraph("AI Compliance Assessment Report", styles['CoverSubtitle']))

    elements.append(Spacer(1, 0.5*inch))

    # Horizontal line
    elements.append(HRFlowable(
        width="80%",
        thickness=2,
        color=COLORS['accent'],
        spaceAfter=30
    ))

    # Assessment details table
    risk_score = data.get('risk_score', 0)
    severity_color, severity_bg, severity_label = get_severity_color(risk_score / 10)

    details = [
        ['Assessment ID:', data.get('assessment_id', 'N/A')],
        ['Risk Score:', f"{risk_score}/100"],
        ['Risk Level:', severity_label],
        ['Assessment Date:', data.get('assessment_date', datetime.now().strftime('%Y-%m-%d'))],
        ['Total Violations:', str(data.get('total_violations', 0))],
        ['Frameworks Assessed:', ', '.join(data.get('frameworks', []))],
        ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
    ]

    detail_table = Table(details, colWidths=[2*inch, 4*inch])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), COLORS['text_muted']),
        ('TEXTCOLOR', (1, 0), (1, -1), COLORS['text']),
        ('TEXTCOLOR', (1, 1), (1, 1), severity_color),  # Risk score color
        ('TEXTCOLOR', (1, 2), (1, 2), severity_color),  # Risk level color
        ('FONTNAME', (1, 1), (1, 2), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))

    elements.append(detail_table)

    elements.append(Spacer(1, 1*inch))

    # Risk score badge/indicator
    risk_table = Table([[f"RISK LEVEL: {severity_label}"]], colWidths=[3*inch])
    risk_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), severity_color),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 16),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(risk_table)

    elements.append(PageBreak())
    return elements


def create_executive_summary(styles, data):
    """Generate executive summary section"""
    elements = []

    elements.append(Paragraph("Executive Summary", styles['SectionHeading']))

    # Summary paragraph
    violations = data.get('violations', [])
    p0_count = sum(1 for v in violations if parse_severity(v.get('severity')) >= 8)
    p1_count = sum(1 for v in violations if 6 <= parse_severity(v.get('severity')) < 8)
    p2_count = sum(1 for v in violations if parse_severity(v.get('severity')) < 6)

    summary_text = f"""
    This assessment identified <b>{len(violations)}</b> compliance violations across
    <b>{len(data.get('frameworks', []))}</b> regulatory frameworks. The findings include
    <b>{p0_count}</b> critical priority items requiring immediate attention,
    <b>{p1_count}</b> high priority items, and <b>{p2_count}</b> medium priority items.
    Estimated remediation timeline: <b>3 months</b> assuming parallel execution.
    """
    elements.append(Paragraph(summary_text, styles['BodyText']))

    elements.append(Spacer(1, 0.3*inch))

    # Priority breakdown table
    elements.append(Paragraph("Violation Breakdown by Priority", styles['SubsectionHeading']))

    priority_data = [
        ['Priority', 'Count', 'Complexity', 'Timeline'],
        ['P0 (Critical)', str(p0_count), 'High', 'Immediate (0-14 days)'],
        ['P1 (High)', str(p1_count), 'Medium', 'Short-term (15-30 days)'],
        ['P2 (Medium)', str(p2_count), 'Low', 'Medium-term (30-90 days)'],
    ]

    priority_table = Table(priority_data, colWidths=[1.5*inch, 1*inch, 1.2*inch, 2*inch])
    priority_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
        ('BACKGROUND', (0, 1), (-1, 1), COLORS['critical_bg']),
        ('BACKGROUND', (0, 2), (-1, 2), COLORS['high_bg']),
        ('BACKGROUND', (0, 3), (-1, 3), COLORS['medium_bg']),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(priority_table)

    elements.append(Spacer(1, 0.3*inch))

    # Violations by framework
    elements.append(Paragraph("Violations by Framework", styles['SubsectionHeading']))

    framework_counts = {}
    for v in violations:
        fw = get_violation_field(v, 'framework', 'regulation', default='Unknown')
        framework_counts[fw] = framework_counts.get(fw, 0) + 1

    fw_data = [['Framework', 'Count']]
    for fw, count in framework_counts.items():
        fw_data.append([fw, str(count)])

    fw_table = Table(fw_data, colWidths=[3*inch, 1*inch])
    fw_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLORS['primary']),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(fw_table)

    elements.append(Spacer(1, 0.4*inch))

    # Top 3 Critical Issues
    elements.append(Paragraph("Top 3 Critical Issues - Immediate Action Required", styles['SubsectionHeading']))

    # Sort by severity and get top 3
    sorted_violations = sorted(violations, key=lambda x: parse_severity(x.get('severity')), reverse=True)[:3]

    for i, v in enumerate(sorted_violations, 1):
        severity = v.get('severity')
        severity_color, _, severity_label = get_severity_color(severity)

        # Use helper for all fields
        title = get_violation_field(v, 'article_violated', 'title', 'violation', 'article_title', 'name')
        article = get_violation_field(v, 'article_violated', 'article', 'citation', 'regulatory_citation', 'article_reference')
        description = get_violation_field(v, 'issue', 'description', 'details', 'violation_description', 'issue_description')
        impact = get_violation_field(v, 'business_impact', 'impact', 'business_risk', default='Impact assessment required')
        framework = get_violation_field(v, 'framework', 'regulation', default='Unknown')

        # Get first remediation step
        remediation = v.get('remediation_steps') or v.get('remediation') or v.get('steps') or []
        first_step = remediation[0] if remediation else 'Review and address'

        issue_text = f"""
        <b>{i}. {framework} Violation - {title}</b><br/>
        <font color="{COLORS['text_muted'].hexval()}">Regulatory Citation: {article}</font><br/>
        <font color="{severity_color.hexval()}">Risk Level: {severity_label} (Severity: {severity}/10)</font><br/>
        <b>Issue:</b> {description}<br/>
        <b>Business Impact:</b> {impact}<br/>
        <b>Immediate Action:</b> {first_step}
        """
        elements.append(Paragraph(issue_text, styles['BodyText']))
        elements.append(Spacer(1, 0.15*inch))

    elements.append(PageBreak())
    return elements


def create_violation_page(styles, violation, index, total):
    """Generate a detailed violation page"""
    elements = []

    # Use helper to get fields with fallbacks
    title = get_violation_field(violation, 'article_violated', 'title', 'violation', 'article_title', 'name')
    description = get_violation_field(violation, 'issue', 'description', 'details', 'violation_description', 'issue_description', 'finding')
    article = get_violation_field(violation, 'article', 'citation', 'article_violated', 'regulatory_citation', 'article_reference', 'regulation')
    framework = get_violation_field(violation, 'framework', 'regulation', 'framework_name', default='Unknown')
    evidence = get_violation_field(violation, 'evidence', 'evidence_quote', 'evidence_text', 'supporting_evidence', default='See document analysis above')
    business_impact = get_violation_field(violation, 'business_impact', 'impact', 'business_risk', default='Impact assessment required')
    eng_scope = get_violation_field(violation, 'engineering_scope', 'scope', 'technical_scope', 'remediation_scope', default='1-2 engineers; review required')

    severity = violation.get('severity')
    severity_color, severity_bg, severity_label = get_severity_color(severity)
    priority, timeline = get_priority_label(severity)

    # Violation header
    header_text = f"Violation {index} of {total}"
    elements.append(Paragraph(header_text, styles['Label']))

    # Framework and title
    title_text = f"{framework} - {title}"
    elements.append(Paragraph(title_text, styles['ViolationTitle']))

    # Severity badge
    badge_table = Table([[severity_label]], colWidths=[1.2*inch])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), severity_color),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(badge_table)
    elements.append(Spacer(1, 0.2*inch))

    # Metadata grid
    metadata = [
        ['Framework:', framework,
         'Article:', article],
        ['Severity:', f"{severity}/10",
         'Priority:', priority],
        ['Complexity:', violation.get('complexity', 'Medium'),
         'Timeline:', timeline],
        ['Confidence:', f"{format_confidence(violation.get('confidence_score', violation.get('confidence', 0.95)))}%", '', ''],
    ]

    meta_table = Table(metadata, colWidths=[1*inch, 1.8*inch, 1*inch, 1.8*inch])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), COLORS['text_muted']),
        ('TEXTCOLOR', (2, 0), (2, -1), COLORS['text_muted']),
        ('TEXTCOLOR', (1, 0), (1, -1), COLORS['text']),
        ('TEXTCOLOR', (3, 0), (3, -1), COLORS['text']),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (-1, -1), COLORS['border']),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 0.2*inch))

    # Description
    elements.append(Paragraph("<b>Description</b>", styles['Label']))
    elements.append(Paragraph(description, styles['BodyText']))

    # Evidence
    elements.append(Paragraph("<b>Evidence</b>", styles['Label']))
    elements.append(Paragraph(evidence, styles['BodyText']))

    # Business Impact
    elements.append(Paragraph("<b>Business Impact</b>", styles['Label']))
    elements.append(Paragraph(business_impact, styles['BodyText']))

    # Engineering Scope
    elements.append(Paragraph("<b>Engineering Scope</b>", styles['Label']))
    elements.append(Paragraph(eng_scope, styles['BodyText']))

    # Remediation Steps
    elements.append(Paragraph("<b>Remediation Steps</b>", styles['Label']))
    steps = violation.get('remediation_steps', ['Review and address the violation'])
    for i, step in enumerate(steps, 1):
        elements.append(Paragraph(f"{i}. {step}", styles['BodyText']))

    # Risk Factors
    elements.append(Paragraph("<b>Risk Factors</b>", styles['Label']))
    risk_factors = violation.get('risk_factors', ['Regulatory enforcement risk'])
    for factor in risk_factors:
        elements.append(Paragraph(f"• {factor}", styles['BodyText']))

    # Dependencies
    elements.append(Paragraph("<b>Dependencies</b>", styles['Label']))
    dependencies = violation.get('dependencies', ['Legal department availability'])
    for dep in dependencies:
        elements.append(Paragraph(f"• {dep}", styles['BodyText']))

    elements.append(PageBreak())
    return elements


def create_remediation_roadmap(styles, data):
    """Generate 90-day remediation roadmap"""
    elements = []

    elements.append(Paragraph("90-Day Remediation Roadmap", styles['SectionHeading']))

    intro_text = """
    This remediation roadmap prioritizes violations based on severity, complexity, and regulatory
    deadlines. Items are organized into three implementation phases with estimated timelines.
    """
    elements.append(Paragraph(intro_text, styles['BodyText']))

    violations = data.get('violations', [])

    # Phase 1: Critical (P0)
    p0_violations = [v for v in violations if parse_severity(v.get('severity')) >= 8]
    if p0_violations:
        elements.append(Paragraph(
            "Phase 1: Immediate Actions (Days 0-14) - Critical Priority",
            styles['SubsectionHeading']
        ))

        phase1_data = [['#', 'Action Item', 'Framework', 'Timeline']]
        for i, v in enumerate(p0_violations, 1):
            # Use helper to get fields with fallbacks
            title = get_violation_field(v, 'article_violated', 'title', 'violation', 'article_title', 'name')
            framework = get_violation_field(v, 'framework', 'regulation', default='N/A')

            # Use first remediation step as action item
            remediation = v.get('remediation_steps') or v.get('remediation') or v.get('steps') or []
            action_item = remediation[0] if remediation else title
            action_text = Paragraph(action_item, styles['BodyText'])
            phase1_data.append([
                str(i),
                action_text,
                framework,
                '6-12 weeks'
            ])

        phase1_table = Table(phase1_data, colWidths=[0.4*inch, 3.5*inch, 0.9*inch, 0.9*inch])
        phase1_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['critical']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
            ('BACKGROUND', (0, 1), (-1, -1), COLORS['critical_bg']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (3, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (1, 1), (1, -1), 8),
            ('RIGHTPADDING', (1, 1), (1, -1), 8),
        ]))
        elements.append(phase1_table)
        elements.append(Spacer(1, 0.2*inch))

    # Phase 2: High (P1)
    p1_violations = [v for v in violations if 6 <= parse_severity(v.get('severity')) < 8]
    if p1_violations:
        elements.append(Paragraph(
            "Phase 2: Short-term Actions (Days 15-30) - High Priority",
            styles['SubsectionHeading']
        ))

        phase2_data = [['#', 'Action Item', 'Framework', 'Timeline']]
        for i, v in enumerate(p1_violations, 1):
            # Use helper to get fields with fallbacks
            title = get_violation_field(v, 'article_violated', 'title', 'violation', 'article_title', 'name')
            framework = get_violation_field(v, 'framework', 'regulation', default='N/A')

            # Use first remediation step as action item
            remediation = v.get('remediation_steps') or v.get('remediation') or v.get('steps') or []
            action_item = remediation[0] if remediation else title
            action_text = Paragraph(action_item, styles['BodyText'])
            phase2_data.append([
                str(i),
                action_text,
                framework,
                '3-6 weeks'
            ])

        phase2_table = Table(phase2_data, colWidths=[0.4*inch, 3.5*inch, 0.9*inch, 0.9*inch])
        phase2_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['high']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
            ('BACKGROUND', (0, 1), (-1, -1), COLORS['high_bg']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (3, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (1, 1), (1, -1), 8),
            ('RIGHTPADDING', (1, 1), (1, -1), 8),
        ]))
        elements.append(phase2_table)
        elements.append(Spacer(1, 0.2*inch))

    # Phase 3: Medium (P2)
    p2_violations = [v for v in violations if parse_severity(v.get('severity')) < 6]
    if p2_violations:
        elements.append(Paragraph(
            "Phase 3: Medium-term Actions (Days 30-90) - Medium Priority",
            styles['SubsectionHeading']
        ))

        phase3_data = [['#', 'Action Item', 'Framework', 'Timeline']]
        for i, v in enumerate(p2_violations, 1):
            # Use helper to get fields with fallbacks
            title = get_violation_field(v, 'article_violated', 'title', 'violation', 'article_title', 'name')
            framework = get_violation_field(v, 'framework', 'regulation', default='N/A')

            # Use first remediation step as action item
            remediation = v.get('remediation_steps') or v.get('remediation') or v.get('steps') or []
            action_item = remediation[0] if remediation else title
            action_text = Paragraph(action_item, styles['BodyText'])
            phase3_data.append([
                str(i),
                action_text,
                framework,
                '1-3 weeks'
            ])

        phase3_table = Table(phase3_data, colWidths=[0.4*inch, 3.5*inch, 0.9*inch, 0.9*inch])
        phase3_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLORS['medium']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, COLORS['border']),
            ('BACKGROUND', (0, 1), (-1, -1), COLORS['medium_bg']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (3, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (1, 1), (1, -1), 8),
            ('RIGHTPADDING', (1, 1), (1, -1), 8),
        ]))
        elements.append(phase3_table)

    elements.append(PageBreak())
    return elements


def create_technical_appendix(styles, data):
    """Generate technical appendix"""
    elements = []

    elements.append(Paragraph("Technical Appendix", styles['SectionHeading']))

    # Assessment Methodology
    elements.append(Paragraph("Assessment Methodology", styles['SubsectionHeading']))
    methodology_text = """
    This compliance assessment was conducted using the Sovereign AI Compliance Scanner.
    Each violation is assessed for severity (1-10 scale), confidence (0-1 scale), and
    complexity (Low/Medium/High). The system employs:

    • <b>RAG-Enhanced Analysis:</b> Retrieval-Augmented Generation with Pinecone vector database
      for semantic search across regulatory documents.

    • <b>Specialized Compliance Judges:</b> 9 AI judges trained on specific regulatory articles
      and enforcement precedents.

    • <b>Confidence Scoring:</b> Each violation includes a confidence score based on evidence
      strength and regulatory precedent alignment.
    """
    elements.append(Paragraph(methodology_text, styles['BodyText']))

    elements.append(Spacer(1, 0.2*inch))

    # Risk Score Calculation
    elements.append(Paragraph("Risk Score Calculation", styles['SubsectionHeading']))
    risk_calc_text = """
    The overall risk score (0-100) is calculated using weighted severity:

    <b>Risk Score = Σ (Severity Weight × Confidence)</b>

    Where:
    • CRITICAL = 40 points (max)
    • MAJOR = 25 points (max)
    • MINOR = 10 points (max)

    <b>Risk Levels:</b>
    • 0-25: Low Risk (Green)
    • 26-50: Medium Risk (Orange)
    • 51-75: High Risk (Dark Orange)
    • 76-100: Critical Risk (Red)
    """
    elements.append(Paragraph(risk_calc_text, styles['BodyText']))

    elements.append(Spacer(1, 0.2*inch))

    # Regulatory Frameworks
    elements.append(Paragraph("Regulatory Frameworks", styles['SubsectionHeading']))
    frameworks_text = """
    • <b>GDPR</b> (General Data Protection Regulation) - Regulation (EU) 2016/679
    • <b>HIPAA</b> Privacy Rule - Protected health information
    • <b>SOX</b> (Sarbanes-Oxley Act) - Section 302, 404 Internal controls
    • <b>CCPA</b> - California Consumer Privacy Act
    • <b>EU AI Act</b> - Regulation (EU) 2024/1689 on Artificial Intelligence
    • <b>EEOC</b> - Employment discrimination in hiring
    """
    elements.append(Paragraph(frameworks_text, styles['BodyText']))

    elements.append(Spacer(1, 0.3*inch))

    # Disclaimer
    elements.append(Paragraph("Disclaimer", styles['SubsectionHeading']))
    disclaimer_text = """
    This report is generated by an AI-powered compliance assessment tool and should not be
    considered legal advice. All findings should be reviewed by qualified legal counsel before
    taking remediation action. The complexity and priority assessments are estimates based on
    typical implementation patterns and may vary based on specific organizational context.
    """
    elements.append(Paragraph(disclaimer_text, styles['BodyText']))

    return elements


# ============================================
# MAIN REPORT GENERATOR
# ============================================
def generate_compliance_report(data, output_path=None):
    """
    Generate a professional compliance report PDF

    Args:
        data: dict containing:
            - assessment_id: str
            - risk_score: int (0-100)
            - frameworks: list of str
            - violations: list of dicts with:
                - framework: str
                - article: str
                - title: str
                - description: str
                - severity: int (1-10)
                - confidence: int (0-100)
                - complexity: str (Low/Medium/High)
                - evidence: str
                - business_impact: str
                - engineering_scope: str
                - remediation_steps: list of str
                - risk_factors: list of str
                - dependencies: list of str
        output_path: str, optional path for output file

    Returns:
        bytes if no output_path, otherwise writes to file
    """

    # Set defaults
    data.setdefault('assessment_id', f"assess_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    data.setdefault('risk_score', 0)
    data.setdefault('frameworks', [])
    data.setdefault('violations', [])
    data.setdefault('total_violations', len(data.get('violations', [])))
    data.setdefault('assessment_date', datetime.now().strftime('%Y-%m-%d'))

    # CRITICAL: Preprocess violations to fix Article 5 severity, confidence format, business impact
    print(f"DEBUG: Preprocessing {len(data['violations'])} violations")
    data['violations'] = preprocess_violations(data['violations'])
    print(f"DEBUG: After preprocessing: {len(data['violations'])} violations (deduplicated)")

    # Create buffer or file
    if output_path:
        buffer = output_path
    else:
        buffer = BytesIO()

    # Create document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=50,
        leftMargin=50,
        topMargin=60,
        bottomMargin=60
    )

    styles = get_custom_styles()
    elements = []

    # Build report sections
    elements.extend(create_cover_page(styles, data))
    elements.extend(create_executive_summary(styles, data))

    # Individual violation pages
    violations = data.get('violations', [])
    for i, violation in enumerate(violations, 1):
        elements.extend(create_violation_page(styles, violation, i, len(violations)))

    # Remediation roadmap
    elements.extend(create_remediation_roadmap(styles, data))

    # Technical appendix
    elements.extend(create_technical_appendix(styles, data))

    # Build PDF with custom page template
    template = ReportTemplate(doc, data['assessment_id'])
    doc.build(elements, onFirstPage=template.on_page, onLaterPages=template.on_page)

    if output_path:
        return output_path
    else:
        buffer.seek(0)
        return buffer


# ============================================
# EXAMPLE USAGE
# ============================================
if __name__ == "__main__":
    # Example data
    example_data = {
        "assessment_id": "assess_20251208_150906_9d32817d",
        "risk_score": 85,
        "frameworks": ["GDPR", "SOX"],
        "violations": [
            {
                "framework": "GDPR",
                "article": "Article 22(4) and Article 9(1)",
                "title": "Automated processing of genetic data without explicit consent",
                "description": "Automated processing of genetic data (special category) without explicit consent violating Article 22(4) and Article 9(1)",
                "severity": 9,
                "confidence": 95,
                "complexity": "High",
                "evidence": "System processes genetic data without consent mechanisms",
                "business_impact": "GDPR fines up to €20M or 4% annual turnover",
                "engineering_scope": "3-5 engineers; solution architect required; security review required; legal review required; DPO involvement required",
                "remediation_steps": [
                    "Immediately cease automated processing of genetic data until explicit consent under Article 9(2)(a) is obtained",
                    "Implement mandatory human review for all decisions with legal effects",
                    "Establish and document retention periods based on legitimate necessity"
                ],
                "risk_factors": [
                    "High visibility - executive scrutiny likely",
                    "Potential for regulatory inquiry if not addressed promptly",
                    "GDPR fines up to €20M - regulatory enforcement risk"
                ],
                "dependencies": [
                    "Legal department availability",
                    "Data Protection Officer approval",
                    "Executive approval and budget allocation"
                ]
            },
            {
                "framework": "SOX",
                "article": "Section 404",
                "title": "Inadequate internal controls over financial reporting",
                "description": "Financial reporting AI that automatically generates quarterly statements without human oversight",
                "severity": 8,
                "confidence": 90,
                "complexity": "High",
                "evidence": "Automated financial report generation without approval workflow",
                "business_impact": "SEC enforcement action, restatement risk",
                "engineering_scope": "2-3 engineers; audit committee involvement required",
                "remediation_steps": [
                    "Implement manual review and approval process for financial statements",
                    "Establish comprehensive internal control framework",
                    "Create segregation of duties protocols"
                ],
                "risk_factors": [
                    "SEC scrutiny possible",
                    "Audit committee concern"
                ],
                "dependencies": [
                    "CFO approval",
                    "External auditor consultation"
                ]
            }
        ]
    }

    # Generate report
    generate_compliance_report(example_data, "example_report.pdf")
    print("Report generated: example_report.pdf")
