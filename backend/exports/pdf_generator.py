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

        # Body text - only add if not already exists
        if 'BodyText' not in self.styles:
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

    def _preprocess_violations(self, violations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Preprocess violations to fix issues before PDF generation.

        Fixes:
        1. Article 5 (EU AI Act Prohibited Practices) always CRITICAL
        2. Deduplicate violations by article
        3. Add specific business impact based on severity/framework
        4. Normalize confidence to 0-1 range
        """
        # Make a copy to avoid modifying original
        violations = [v.copy() for v in violations]

        # Fix 1: Article 5 override - CRITICAL (Prohibited AI Practices)
        for v in violations:
            article = v.get('article_violated', '').lower()
            framework = v.get('framework', '').lower()

            # EU AI Act Article 5 = Prohibited Practices = Always CRITICAL
            if ('article 5' in article or 'article5' in article) and 'eu' in framework:
                v['severity'] = 'CRITICAL'
                v['priority'] = 'P0'
                v['timeline'] = 'Immediate (0-14 days)'
                logger.info(f"Overriding Article 5 violation to CRITICAL: {article}")

        # Fix 2: Deduplicate only TRUE duplicates (same article AND same description/evidence)
        # Before: Just deduped by article, so 3 different Art.22 violations became 1
        # After: Include description hash in key so only identical violations are deduped
        unique_violations = {}
        for v in violations:
            article = v.get('article_violated', 'Unknown')
            framework = v.get('framework', 'Unknown')
            # Include first 50 chars of description/issue to differentiate violations about same article
            description = str(v.get('issue', v.get('description', '')))[:50]
            evidence = str(v.get('evidence_quote', v.get('evidence', '')))[:50]
            key = f"{framework}-{article}-{hash(description + evidence)}"

            if key not in unique_violations or v.get('confidence', 0) > unique_violations[key].get('confidence', 0):
                unique_violations[key] = v

        violations = list(unique_violations.values())

        # Fix 3: Add specific business impact if missing
        for v in violations:
            if not v.get('business_impact') or v.get('business_impact') == 'Impact assessment required':
                v['business_impact'] = self._get_default_business_impact(
                    v.get('severity', 'UNKNOWN'),
                    v.get('framework', 'Unknown')
                )

        # Fix 4: Normalize confidence to 0-1 range
        for v in violations:
            conf = v.get('confidence', 0.0)
            if conf > 1:  # If confidence is already in percentage (e.g., 92)
                v['confidence'] = conf / 100

        return violations

    def _get_default_business_impact(self, severity: str, framework: str) -> str:
        """Get specific business impact based on severity and framework."""
        framework_lower = framework.lower()

        if severity == 'CRITICAL':
            if 'gdpr' in framework_lower:
                return 'Up to €20M or 4% of annual global turnover. Immediate regulatory action likely. Public disclosure required.'
            elif 'eu' in framework_lower or 'ai' in framework_lower:
                return 'Up to €35M or 7% of annual global turnover. Product ban possible. Mandatory notification to authorities.'
            elif 'sox' in framework_lower:
                return 'SEC enforcement action. Officer criminal liability. Trading suspension risk. Investor lawsuits.'
            else:
                return 'Severe regulatory penalties. Operational shutdown risk. Executive liability.'

        elif severity == 'MAJOR':
            if 'gdpr' in framework_lower:
                return 'Up to €10M or 2% of annual global turnover. Data protection authority investigation.'
            elif 'eu' in framework_lower or 'ai' in framework_lower:
                return 'Up to €15M or 3% of annual global turnover. Product restrictions possible.'
            elif 'sox' in framework_lower:
                return 'SEC investigation. Restatement requirements. Material weakness disclosure.'
            else:
                return 'Significant regulatory penalties. Compliance review required.'

        elif severity == 'MINOR':
            return 'Regulatory warning. Corrective action required. Limited financial exposure.'

        else:
            return 'Compliance review recommended. Risk mitigation advised.'

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
        # Preprocess violations: fix Article 5 severity, deduplicate, add business impact
        violations = self._preprocess_violations(violations)

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

        # 90-day remediation roadmap
        if violations:
            story.append(PageBreak())
            story.extend(self._build_remediation_roadmap(violations))

        # Technical appendix
        story.append(PageBreak())
        story.extend(self._build_technical_appendix(violations, frameworks))

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
            [Paragraph("Report Date:", self.styles['BodyText']), Paragraph(datetime.now().strftime("%B %d, %Y at %H:%M UTC"), self.styles['BodyText'])],
            [Paragraph("Analysis ID:", self.styles['BodyText']), Paragraph(analysis_id or "N/A", self.styles['BodyText'])],
            [Paragraph("Frameworks:", self.styles['BodyText']), Paragraph(", ".join(f.upper() for f in frameworks), self.styles['BodyText'])],
            [Paragraph("Risk Score:", self.styles['BodyText']), Paragraph(self._format_risk_score(risk_score), self.styles['BodyText'])]
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
            ('WORDWRAP', (0, 0), (-1, -1), 'LTR'),
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

        # Priority breakdown table (P0/P1/P2)
        if total_violations > 0:
            elements.append(Paragraph(
                "Priority Breakdown",
                self.styles['SubsectionHeader']
            ))

            priority_data = [
                ['Priority', 'Timeline', 'Count', 'Description'],
                ['P0', 'Immediate', str(critical_count), 'Critical legal/regulatory risk - fix now'],
                ['P1', '30 days', str(major_count), 'Significant compliance gap - address soon'],
                ['P2', '90 days', str(minor_count), 'Minor improvement - scheduled fix']
            ]

            priority_table = Table(priority_data, colWidths=[0.8*inch, 1*inch, 0.8*inch, 3.4*inch])
            priority_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))

            elements.append(priority_table)
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
                fw_data.append([fw.upper(), str(count)])

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
            elements.append(Spacer(1, 0.3 * inch))

        # Top 3 Critical Issues
        critical_violations = [v for v in violations if v.get('severity') == 'CRITICAL']
        if critical_violations:
            elements.append(Paragraph(
                "Top Critical Issues (Immediate Action Required)",
                self.styles['SubsectionHeader']
            ))
            elements.append(Spacer(1, 0.1 * inch))

            for i, violation in enumerate(critical_violations[:3], 1):
                article = violation.get('article_violated', 'Unknown Article')
                framework = violation.get('framework', 'Unknown').upper()
                evidence = violation.get('evidence_quote', 'No evidence')[:150]

                issue_text = f"<b>{i}. {framework} - {article}</b><br/>{evidence}..."
                elements.append(Paragraph(issue_text, self.styles['BodyText']))
                elements.append(Spacer(1, 0.15 * inch))

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
            # Add pagebreak before each violation (except first)
            if i > 1:
                elements.append(PageBreak())

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

        # Confidence - convert to percentage (0.92 -> 92%)
        confidence_percent = int(confidence * 100) if confidence <= 1 else int(confidence)
        elements.append(Paragraph(
            f"<b>Confidence:</b> {confidence_percent}%",
            self.styles['BodyText']
        ))
        elements.append(Spacer(1, 0.1 * inch))

        # Business Impact (now showing specific consequences instead of generic text)
        business_impact = violation.get('business_impact', 'Impact assessment required')
        elements.append(Paragraph("<b>Business Impact:</b>", self.styles['BodyText']))
        elements.append(Paragraph(
            business_impact,
            self.styles['BodyText']
        ))

        return elements

    def _build_remediation_roadmap(self, violations: List[Dict[str, Any]]) -> List:
        """Build 90-day remediation roadmap with phases."""
        elements = []

        elements.append(Paragraph(
            "90-Day Remediation Roadmap",
            self.styles['SectionHeader']
        ))
        elements.append(Spacer(1, 0.2 * inch))

        intro_text = """
        This roadmap provides a phased approach to addressing compliance violations,
        prioritized by severity and regulatory impact. Each phase includes specific
        action items and expected outcomes.
        """
        elements.append(Paragraph(intro_text, self.styles['BodyText']))
        elements.append(Spacer(1, 0.3 * inch))

        # Phase 1: Immediate (P0 - CRITICAL)
        critical_violations = [v for v in violations if v.get('severity') == 'CRITICAL']
        if critical_violations:
            elements.append(Paragraph(
                "Phase 1: Immediate Action (Days 1-7) - P0 Critical",
                self.styles['SubsectionHeader']
            ))

            for i, violation in enumerate(critical_violations, 1):
                article = violation.get('article_violated', 'Unknown')
                framework = violation.get('framework', 'Unknown').upper()
                steps = violation.get('remediation_steps', [])

                elements.append(Paragraph(
                    f"<b>{i}. {framework} - {article}</b>",
                    self.styles['BodyText']
                ))

                for step in steps[:3]:  # Show top 3 steps
                    elements.append(Paragraph(f"  • {step}", self.styles['BodyText']))

                elements.append(Spacer(1, 0.1 * inch))

            elements.append(Spacer(1, 0.2 * inch))

        # Phase 2: Short-term (P1 - MAJOR)
        major_violations = [v for v in violations if v.get('severity') == 'MAJOR']
        if major_violations:
            elements.append(Paragraph(
                "Phase 2: Short-term Fixes (Days 8-30) - P1 Major",
                self.styles['SubsectionHeader']
            ))

            for i, violation in enumerate(major_violations, 1):
                article = violation.get('article_violated', 'Unknown')
                framework = violation.get('framework', 'Unknown').upper()
                steps = violation.get('remediation_steps', [])

                elements.append(Paragraph(
                    f"<b>{i}. {framework} - {article}</b>",
                    self.styles['BodyText']
                ))

                for step in steps[:2]:  # Show top 2 steps
                    elements.append(Paragraph(f"  • {step}", self.styles['BodyText']))

                elements.append(Spacer(1, 0.1 * inch))

            elements.append(Spacer(1, 0.2 * inch))

        # Phase 3: Long-term (P2 - MINOR)
        minor_violations = [v for v in violations if v.get('severity') == 'MINOR']
        if minor_violations:
            elements.append(Paragraph(
                "Phase 3: Long-term Improvements (Days 31-90) - P2 Minor",
                self.styles['SubsectionHeader']
            ))

            for i, violation in enumerate(minor_violations, 1):
                article = violation.get('article_violated', 'Unknown')
                framework = violation.get('framework', 'Unknown').upper()

                elements.append(Paragraph(
                    f"<b>{i}. {framework} - {article}</b>",
                    self.styles['BodyText']
                ))

                elements.append(Spacer(1, 0.1 * inch))

            elements.append(Spacer(1, 0.2 * inch))

        return elements

    def _build_technical_appendix(
        self,
        violations: List[Dict[str, Any]],
        frameworks: List[str]
    ) -> List:
        """Build technical appendix with methodology and references."""
        elements = []

        elements.append(Paragraph(
            "Technical Appendix",
            self.styles['SectionHeader']
        ))
        elements.append(Spacer(1, 0.2 * inch))

        # Methodology
        elements.append(Paragraph(
            "Analysis Methodology",
            self.styles['SubsectionHeader']
        ))

        methodology_text = """
        This compliance analysis was performed using Sovereign V5, an AI-powered
        regulatory intelligence platform. The system employs:
        <br/><br/>
        <b>1. RAG-Enhanced Analysis:</b> Retrieval-Augmented Generation (RAG) with
        Pinecone vector database for semantic search across regulatory documents.
        <br/><br/>
        <b>2. Specialized Compliance Judges:</b> 9 AI judges trained on specific
        regulatory articles and enforcement precedents:
        <br/>
          • GDPR: Article 22 (Automated Decision-Making), Article 17 (Right to Erasure),
            Article 32 (Security of Processing)
        <br/>
          • SOX: Section 404 (Internal Controls), Section 302 (Corporate Responsibility),
            Audit Trail Requirements
        <br/>
          • EU AI Act: High-Risk AI Systems, Prohibited Practices, Transparency Requirements
        <br/><br/>
        <b>3. Confidence Scoring:</b> Each violation includes a confidence score
        (0-100%) based on evidence strength and regulatory precedent alignment.
        """
        elements.append(Paragraph(methodology_text, self.styles['BodyText']))
        elements.append(Spacer(1, 0.3 * inch))

        # Risk Scoring Formula
        elements.append(Paragraph(
            "Risk Score Calculation",
            self.styles['SubsectionHeader']
        ))

        risk_formula_text = """
        The overall risk score (0-100) is calculated using weighted severity:
        <br/><br/>
        Risk Score = Σ (Severity Weight × Confidence)
        <br/><br/>
        Where:
        <br/>
          • CRITICAL = 40 points (max)
        <br/>
          • MAJOR = 25 points (max)
        <br/>
          • MINOR = 10 points (max)
        <br/><br/>
        Risk Levels:
        <br/>
          • 0-25: Low Risk (Green)
        <br/>
          • 26-50: Medium Risk (Orange)
        <br/>
          • 51-75: High Risk (Dark Orange)
        <br/>
          • 76-100: Critical Risk (Red)
        """
        elements.append(Paragraph(risk_formula_text, self.styles['BodyText']))
        elements.append(Spacer(1, 0.3 * inch))

        # Regulatory References
        elements.append(Paragraph(
            "Regulatory References",
            self.styles['SubsectionHeader']
        ))

        references_text = """
        <b>GDPR (General Data Protection Regulation):</b>
        <br/>
        Regulation (EU) 2016/679 - Official Journal of the European Union
        <br/><br/>
        <b>SOX (Sarbanes-Oxley Act):</b>
        <br/>
        Public Company Accounting Reform and Investor Protection Act of 2002
        <br/><br/>
        <b>EU AI Act:</b>
        <br/>
        Regulation (EU) 2024/1689 on Artificial Intelligence
        <br/><br/>
        <i>For questions or clarifications, consult with qualified legal counsel
        specializing in regulatory compliance.</i>
        """
        elements.append(Paragraph(references_text, self.styles['BodyText']))

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
