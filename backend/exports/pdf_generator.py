"""
PDF Export Generator for Sovereign V5

Generates professional compliance reports with executive summary,
violation details, and remediation steps using ReportLab.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

logger = logging.getLogger(__name__)


class PDFComplianceReport:
    """
    Generates professional PDF compliance reports.

    Report structure:
    1. Title page with executive summary
    2. Risk score visualization
    3. Detailed violation findings
    4. Remediation recommendations
    """

    def __init__(self):
        """Initialize PDF generator with styles."""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles for the report."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=20,
            spaceAfter=12,
            fontName='Helvetica-Bold'
        ))

        # Subsection header
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#34495e'),
            spaceBefore=12,
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))

        # Body text
        self.styles.add(ParagraphStyle(
            name='BodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#2c3e50'),
            alignment=TA_JUSTIFY,
            spaceAfter=6
        ))

        # Critical alert
        self.styles.add(ParagraphStyle(
            name='CriticalAlert',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#c0392b'),
            fontName='Helvetica-Bold',
            spaceAfter=6
        ))

    def generate_report(
        self,
        violations: List[Dict[str, Any]],
        risk_score: int,
        frameworks: List[str],
        submission_preview: str,
        analysis_id: str = None
    ) -> BytesIO:
        """
        Generate complete PDF compliance report.

        Args:
            violations: List of detected violations.
            risk_score: Overall risk score (0-100).
            frameworks: Frameworks analyzed.
            submission_preview: Preview of analyzed submission.
            analysis_id: Unique analysis identifier.

        Returns:
            BytesIO buffer containing PDF document.
        """
        buffer = BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        # Build document content
        story = []

        # Title page
        story.extend(self._build_title_page(
            analysis_id, frameworks, risk_score
        ))
        story.append(PageBreak())

        # Executive summary
        story.extend(self._build_executive_summary(
            violations, risk_score, frameworks
        ))
        story.append(PageBreak())

        # Detailed findings
        story.extend(self._build_detailed_findings(violations))

        # Remediation recommendations
        if violations:
            story.append(PageBreak())
            story.extend(self._build_remediation_section(violations))

        # Build PDF
        doc.build(story)
        buffer.seek(0)

        logger.info(f"Generated PDF report with {len(violations)} violations")
        return buffer

    def _build_title_page(
        self,
        analysis_id: str,
        frameworks: List[str],
        risk_score: int
    ) -> List:
        """Build the title page."""
        elements = []

        # Title
        elements.append(Spacer(1, 1.5 * inch))
        elements.append(Paragraph(
            "AI Compliance Intelligence Report",
            self.styles['CustomTitle']
        ))

        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(
            "Sovereign V5 - Regulatory Compliance Analysis",
            self.styles['BodyText']
        ))

        elements.append(Spacer(1, 0.5 * inch))

        # Analysis metadata table
        metadata = [
            ["Report Date:", datetime.now().strftime("%B %d, %Y at %H:%M UTC")],
            ["Analysis ID:", analysis_id or "N/A"],
            ["Frameworks:", ", ".join(f.upper() for f in frameworks)],
            ["Risk Score:", self._format_risk_score(risk_score)]
        ]

        table = Table(metadata, colWidths=[2 * inch, 4 * inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#7f8c8d')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2c3e50')),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 1 * inch))

        # Risk classification box
        risk_level = self._get_risk_level(risk_score)
        risk_color = self._get_risk_color(risk_score)

        risk_text = f"<b>RISK LEVEL: {risk_level}</b>"
        risk_para = Paragraph(risk_text, self.styles['BodyText'])

        risk_table = Table([[risk_para]], colWidths=[5 * inch])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), risk_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#2c3e50'))
        ]))

        elements.append(risk_table)

        return elements

    def _build_executive_summary(
        self,
        violations: List[Dict[str, Any]],
        risk_score: int,
        frameworks: List[str]
    ) -> List:
        """Build executive summary section."""
        elements = []

        elements.append(Paragraph(
            "Executive Summary",
            self.styles['SectionHeader']
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Summary statistics
        total_violations = len(violations)
        critical_count = sum(1 for v in violations if v.get('severity') == 'CRITICAL')
        major_count = sum(1 for v in violations if v.get('severity') == 'MAJOR')
        minor_count = sum(1 for v in violations if v.get('severity') == 'MINOR')

        if total_violations == 0:
            summary_text = f"""
            This analysis evaluated the submitted system against {', '.join(f.upper() for f in frameworks)}
            regulatory frameworks using 9 specialized AI compliance judges.
            <b>No violations were detected</b>. The system appears to be compliant with the analyzed frameworks.
            """
        else:
            summary_text = f"""
            This analysis evaluated the submitted system against {', '.join(f.upper() for f in frameworks)}
            regulatory frameworks using 9 specialized AI compliance judges.
            The analysis identified <b>{total_violations} potential compliance violation(s)</b>
            with a risk score of <b>{risk_score}/100</b>.
            """

        elements.append(Paragraph(summary_text, self.styles['BodyText']))
        elements.append(Spacer(1, 0.3 * inch))

        # Violation breakdown table
        if total_violations > 0:
            elements.append(Paragraph(
                "Violation Breakdown by Severity",
                self.styles['SubsectionHeader']
            ))

            breakdown_data = [
                ['Severity Level', 'Count', 'Description'],
                ['CRITICAL', str(critical_count), 'Immediate legal/regulatory risk'],
                ['MAJOR', str(major_count), 'Significant compliance gap'],
                ['MINOR', str(minor_count), 'Minor improvement needed']
            ]

            breakdown_table = Table(breakdown_data, colWidths=[1.5*inch, 1*inch, 3.5*inch])
            breakdown_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(breakdown_table)
            elements.append(Spacer(1, 0.3 * inch))

        # Framework breakdown
        framework_counts = {}
        for v in violations:
            fw = v.get('framework', 'Unknown')
            framework_counts[fw] = framework_counts.get(fw, 0) + 1

        if framework_counts:
            elements.append(Paragraph(
                "Violations by Framework",
                self.styles['SubsectionHeader']
            ))

            fw_data = [['Framework', 'Violations']]
            for fw, count in sorted(framework_counts.items()):
                fw_data.append([fw, str(count)])

            fw_table = Table(fw_data, colWidths=[3*inch, 2*inch])
            fw_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(fw_table)

        return elements

    def _build_detailed_findings(self, violations: List[Dict[str, Any]]) -> List:
        """Build detailed findings section."""
        elements = []

        elements.append(Paragraph(
            "Detailed Findings",
            self.styles['SectionHeader']
        ))
        elements.append(Spacer(1, 0.2 * inch))

        if not violations:
            elements.append(Paragraph(
                "No violations detected. The system appears to be compliant with analyzed frameworks.",
                self.styles['BodyText']
            ))
            return elements

        # Sort violations by severity
        severity_order = {'CRITICAL': 0, 'MAJOR': 1, 'MINOR': 2}
        sorted_violations = sorted(
            violations,
            key=lambda v: severity_order.get(v.get('severity', 'MINOR'), 3)
        )

        for i, violation in enumerate(sorted_violations, 1):
            elements.extend(self._build_violation_detail(i, violation))
            elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _build_violation_detail(self, number: int, violation: Dict[str, Any]) -> List:
        """Build a single violation detail block."""
        elements = []

        severity = violation.get('severity', 'UNKNOWN')
        article = violation.get('article_violated', 'Unknown Article')
        framework = violation.get('framework', 'Unknown')
        evidence = violation.get('evidence_quote', 'No evidence provided')
        confidence = violation.get('confidence', 0.0)

        # Violation header
        header_text = f"Finding #{number}: {framework} - {article}"
        elements.append(Paragraph(header_text, self.styles['SubsectionHeader']))

        # Severity badge
        severity_color = self._get_severity_color(severity)
        severity_table = Table([[f"<b>{severity}</b>"]], colWidths=[1.5*inch])
        severity_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), severity_color),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(severity_table)
        elements.append(Spacer(1, 0.1 * inch))

        # Evidence
        elements.append(Paragraph("<b>Evidence:</b>", self.styles['BodyText']))
        elements.append(Paragraph(
            f"<i>\"{evidence}\"</i>",
            self.styles['BodyText']
        ))
        elements.append(Spacer(1, 0.1 * inch))

        # Confidence
        elements.append(Paragraph(
            f"<b>Confidence:</b> {confidence:.1%}",
            self.styles['BodyText']
        ))

        return elements

    def _build_remediation_section(self, violations: List[Dict[str, Any]]) -> List:
        """Build remediation recommendations section."""
        elements = []

        elements.append(Paragraph(
            "Remediation Recommendations",
            self.styles['SectionHeader']
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Group violations by framework for organized recommendations
        framework_violations = {}
        for v in violations:
            fw = v.get('framework', 'Unknown')
            if fw not in framework_violations:
                framework_violations[fw] = []
            framework_violations[fw].append(v)

        for framework, fw_violations in sorted(framework_violations.items()):
            elements.append(Paragraph(
                f"{framework} Remediation Steps",
                self.styles['SubsectionHeader']
            ))

            for i, violation in enumerate(fw_violations, 1):
                article = violation.get('article_violated', 'Unknown')
                steps = violation.get('remediation_steps', [])

                elements.append(Paragraph(
                    f"<b>{i}. {article}</b>",
                    self.styles['BodyText']
                ))

                for step in steps:
                    elements.append(Paragraph(
                        f"• {step}",
                        self.styles['BodyText']
                    ))

                elements.append(Spacer(1, 0.15 * inch))

            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _format_risk_score(self, score: int) -> str:
        """Format risk score with level."""
        level = self._get_risk_level(score)
        return f"{score}/100 ({level})"

    def _get_risk_level(self, score: int) -> str:
        """Get risk level from score."""
        if score <= 25:
            return "LOW"
        elif score <= 50:
            return "MEDIUM"
        elif score <= 75:
            return "HIGH"
        else:
            return "CRITICAL"

    def _get_risk_color(self, score: int) -> colors.Color:
        """Get color for risk level."""
        if score <= 25:
            return colors.HexColor('#27ae60')  # Green
        elif score <= 50:
            return colors.HexColor('#f39c12')  # Orange
        elif score <= 75:
            return colors.HexColor('#e67e22')  # Dark orange
        else:
            return colors.HexColor('#c0392b')  # Red

    def _get_severity_color(self, severity: str) -> colors.Color:
        """Get color for severity level."""
        colors_map = {
            'CRITICAL': colors.HexColor('#c0392b'),
            'MAJOR': colors.HexColor('#e67e22'),
            'MINOR': colors.HexColor('#f39c12'),
            'NONE': colors.HexColor('#27ae60')
        }
        return colors_map.get(severity, colors.grey)


def generate_compliance_pdf(
    violations: List[Dict[str, Any]],
    risk_score: int,
    frameworks: List[str],
    submission_preview: str = "",
    analysis_id: str = None
) -> BytesIO:
    """
    Generate a compliance PDF report.

    Args:
        violations: List of detected violations.
        risk_score: Overall risk score (0-100).
        frameworks: Frameworks analyzed.
        submission_preview: Preview of submission text.
        analysis_id: Unique analysis ID.

    Returns:
        BytesIO buffer containing PDF.
    """
    generator = PDFComplianceReport()
    return generator.generate_report(
        violations=violations,
        risk_score=risk_score,
        frameworks=frameworks,
        submission_preview=submission_preview,
        analysis_id=analysis_id
    )
