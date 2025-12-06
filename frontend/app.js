/**
 * Sovereign V5 - Frontend Application
 * AI Compliance Intelligence Platform
 */

const API_BASE = 'https://sovereign-v5.onrender.com';

// State
let selectedFrameworks = ['gdpr'];
let uploadedFile = null;
let analysisResults = null;

// DOM Elements
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const filePreview = document.getElementById('file-preview');
const fileName = document.getElementById('file-name');
const fileSize = document.getElementById('file-size');
const removeFileBtn = document.getElementById('remove-file');
const textInput = document.getElementById('text-input');
const analyzeBtn = document.getElementById('analyze-btn');
const progressContainer = document.getElementById('progress-container');
const progressFill = document.getElementById('progress-fill');
const progressText = document.getElementById('progress-text');
const inputSection = document.getElementById('input-section');
const resultsSection = document.getElementById('results-section');
const violationsList = document.getElementById('violations-list');
const newAnalysisBtn = document.getElementById('new-analysis-btn');
const exportPdfBtn = document.getElementById('export-pdf');
const exportCsvBtn = document.getElementById('export-csv');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeFrameworkSelection();
    initializeFileUpload();
    initializeAnalysis();
    initializeExports();
    updateAnalyzeButton();
});

// Framework Selection
function initializeFrameworkSelection() {
    const frameworkCards = document.querySelectorAll('.framework-card');

    frameworkCards.forEach(card => {
        card.addEventListener('click', () => {
            const framework = card.dataset.framework;

            if (card.classList.contains('selected')) {
                card.classList.remove('selected');
                card.querySelector('.framework-checkbox').textContent = '';
                selectedFrameworks = selectedFrameworks.filter(f => f !== framework);
            } else {
                card.classList.add('selected');
                card.querySelector('.framework-checkbox').textContent = '✓';
                selectedFrameworks.push(framework);
            }

            updateAnalyzeButton();
        });
    });
}

// File Upload
function initializeFileUpload() {
    // Click to upload
    uploadZone.addEventListener('click', () => fileInput.click());

    // Drag and drop
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Remove file
    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
    });

    // Text input
    textInput.addEventListener('input', updateAnalyzeButton);
}

function handleFile(file) {
    const allowedTypes = ['.pdf', '.txt', '.docx', '.doc'];
    const extension = '.' + file.name.split('.').pop().toLowerCase();

    if (!allowedTypes.includes(extension)) {
        alert('Please upload a PDF, TXT, or DOCX file.');
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        alert('File size must be less than 10MB.');
        return;
    }

    uploadedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    filePreview.classList.add('active');
    uploadZone.style.display = 'none';
    updateAnalyzeButton();
}

function clearFile() {
    uploadedFile = null;
    fileInput.value = '';
    filePreview.classList.remove('active');
    uploadZone.style.display = 'block';
    updateAnalyzeButton();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Analysis
function initializeAnalysis() {
    analyzeBtn.addEventListener('click', runAnalysis);
    newAnalysisBtn.addEventListener('click', resetAnalysis);
}

function updateAnalyzeButton() {
    const hasInput = uploadedFile || textInput.value.trim().length > 0;
    const hasFrameworks = selectedFrameworks.length > 0;
    analyzeBtn.disabled = !(hasInput && hasFrameworks);
}

async function runAnalysis() {
    const description = textInput.value.trim();

    if (!description && !uploadedFile) {
        alert('Please enter a system description or upload a file.');
        return;
    }

    if (selectedFrameworks.length === 0) {
        alert('Please select at least one regulatory framework.');
        return;
    }

    // Show progress
    analyzeBtn.disabled = true;
    progressContainer.classList.add('active');

    try {
        // Simulate progress
        await animateProgress();

        // Get description from file or text input
        let analysisText = description;

        if (uploadedFile && !description) {
            // For now, just use placeholder - in production, parse the file
            analysisText = await readFileAsText(uploadedFile);
        }

        // Call API
        const response = await fetch(`${API_BASE}/api/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                description: analysisText,
                frameworks: selectedFrameworks
            })
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        analysisResults = await response.json();
        displayResults(analysisResults);

    } catch (error) {
        console.error('Analysis failed:', error);
        alert('Analysis failed. Please check your connection and try again.\n\nError: ' + error.message);
        resetProgress();
    }
}

async function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = reject;
        reader.readAsText(file);
    });
}

async function animateProgress() {
    const steps = [
        { progress: 20, text: 'Retrieving regulatory context...' },
        { progress: 40, text: 'Analyzing GDPR compliance...' },
        { progress: 60, text: 'Running compliance judges...' },
        { progress: 80, text: 'Evaluating violations...' },
        { progress: 95, text: 'Generating report...' }
    ];

    for (const step of steps) {
        progressFill.style.width = step.progress + '%';
        progressText.textContent = step.text;
        await sleep(500);
    }
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function resetProgress() {
    progressContainer.classList.remove('active');
    progressFill.style.width = '0%';
    analyzeBtn.disabled = false;
}

// Results Display
function displayResults(results) {
    // Update summary
    const riskScore = results.risk_score || 0;
    document.getElementById('risk-score').textContent = riskScore;
    document.getElementById('risk-score').className = 'summary-value ' + getRiskClass(riskScore);

    document.getElementById('violation-count').textContent = results.violations?.length || 0;
    document.getElementById('critical-count').textContent =
        results.violations?.filter(v => v.severity === 'CRITICAL').length || 0;
    document.getElementById('frameworks-count').textContent =
        results.frameworks_analyzed?.length || 0;

    // Update risk indicator
    document.getElementById('risk-indicator').style.left = riskScore + '%';

    // Render violations
    renderViolations(results.violations || []);

    // Show results section
    inputSection.style.display = 'none';
    resultsSection.classList.add('active');
    progressContainer.classList.remove('active');
}

function getRiskClass(score) {
    if (score <= 25) return 'risk-low';
    if (score <= 50) return 'risk-medium';
    if (score <= 75) return 'risk-high';
    return 'risk-critical';
}

function renderViolations(violations) {
    if (violations.length === 0) {
        violationsList.innerHTML = `
            <div class="no-violations">
                <div class="no-violations-icon">✅</div>
                <h3>No Violations Detected</h3>
                <p>Your system appears to be compliant with the selected frameworks.</p>
            </div>
        `;
        return;
    }

    violationsList.innerHTML = violations.map(violation => `
        <div class="violation-card ${violation.severity.toLowerCase()}">
            <div class="violation-header">
                <div class="violation-title">${violation.article_violated}</div>
                <span class="violation-badge ${violation.severity.toLowerCase()}">${violation.severity}</span>
            </div>
            <div class="violation-meta">
                ${violation.framework} • ${violation.focus_area} • ${Math.round(violation.confidence * 100)}% confidence
            </div>
            <div class="violation-evidence">
                "${violation.evidence_quote}"
            </div>
            <div class="violation-remediation">
                <h4>Remediation Steps:</h4>
                <ul>
                    ${violation.remediation_steps.map(step => `<li>${step}</li>`).join('')}
                </ul>
            </div>
        </div>
    `).join('');
}

function resetAnalysis() {
    resultsSection.classList.remove('active');
    inputSection.style.display = 'block';
    progressFill.style.width = '0%';
    analyzeBtn.disabled = false;
    analysisResults = null;
}

// Exports
function initializeExports() {
    exportPdfBtn.addEventListener('click', exportToPdf);
    exportCsvBtn.addEventListener('click', exportToCsv);
}

function exportToPdf() {
    if (!analysisResults) return;

    // Create printable content
    const printContent = `
        <html>
        <head>
            <title>Sovereign Compliance Report</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; }
                h1 { color: #1e3a5f; }
                .summary { display: flex; gap: 20px; margin: 20px 0; }
                .summary-item { padding: 15px; background: #f8fafc; border-radius: 8px; }
                .violation { border-left: 4px solid; padding: 15px; margin: 15px 0; }
                .critical { border-color: #991b1b; background: #fee2e2; }
                .major { border-color: #c2410c; background: #fff7ed; }
                .minor { border-color: #a16207; background: #fefce8; }
            </style>
        </head>
        <body>
            <h1>Sovereign Compliance Report</h1>
            <p>Generated: ${new Date().toLocaleString()}</p>
            <div class="summary">
                <div class="summary-item"><strong>Risk Score:</strong> ${analysisResults.risk_score}</div>
                <div class="summary-item"><strong>Violations:</strong> ${analysisResults.violations?.length || 0}</div>
                <div class="summary-item"><strong>Frameworks:</strong> ${analysisResults.frameworks_analyzed?.join(', ')}</div>
            </div>
            <h2>Violations</h2>
            ${analysisResults.violations?.map(v => `
                <div class="violation ${v.severity.toLowerCase()}">
                    <strong>${v.article_violated}</strong> (${v.severity})<br>
                    <em>"${v.evidence_quote}"</em><br>
                    <p><strong>Remediation:</strong></p>
                    <ul>${v.remediation_steps.map(s => `<li>${s}</li>`).join('')}</ul>
                </div>
            `).join('') || '<p>No violations found.</p>'}
        </body>
        </html>
    `;

    const printWindow = window.open('', '_blank');
    printWindow.document.write(printContent);
    printWindow.document.close();
    printWindow.print();
}

function exportToCsv() {
    if (!analysisResults || !analysisResults.violations) return;

    const headers = ['Severity', 'Article', 'Framework', 'Focus Area', 'Confidence', 'Evidence', 'Remediation'];
    const rows = analysisResults.violations.map(v => [
        v.severity,
        v.article_violated,
        v.framework,
        v.focus_area,
        Math.round(v.confidence * 100) + '%',
        `"${v.evidence_quote.replace(/"/g, '""')}"`,
        `"${v.remediation_steps.join('; ').replace(/"/g, '""')}"`
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sovereign-compliance-report-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
