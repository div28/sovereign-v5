/**
 * SOVEREIGN V5 - Frontend Application
 * AI Compliance Intelligence Platform
 */

const API_BASE = 'https://sovereign-v5.onrender.com';

// State
let selectedFrameworks = ['gdpr'];
let analysisResults = null;
let charts = {};
let particleSystem = null;
let networkGraph = null;
let animationFrameId = null;

// ============================================================================
// PARTICLE SYSTEM
// ============================================================================

class Particle {
    constructor(canvas) {
        this.canvas = canvas;
        this.reset();
    }

    reset() {
        this.x = Math.random() * this.canvas.width;
        this.y = Math.random() * this.canvas.height;
        this.vx = (Math.random() - 0.5) * 1.5;
        this.vy = (Math.random() - 0.5) * 1.5;
        this.radius = Math.random() * 2 + 1;
        this.opacity = Math.random() * 0.5 + 0.3;
    }

    update() {
        this.x += this.vx;
        this.y += this.vy;

        // Wrap around edges
        if (this.x < 0) this.x = this.canvas.width;
        if (this.x > this.canvas.width) this.x = 0;
        if (this.y < 0) this.y = this.canvas.height;
        if (this.y > this.canvas.height) this.y = 0;
    }

    draw(ctx) {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(30, 58, 95, ${this.opacity})`;
        ctx.fill();
    }
}

class ParticleSystem {
    constructor(canvas, particleCount = 120) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.isRunning = false;

        // Set canvas size
        this.resize();
        window.addEventListener('resize', () => this.resize());

        // Create particles
        for (let i = 0; i < particleCount; i++) {
            this.particles.push(new Particle(canvas));
        }
    }

    resize() {
        this.canvas.width = this.canvas.offsetWidth;
        this.canvas.height = this.canvas.offsetHeight;
    }

    start() {
        this.isRunning = true;
        this.animate();
    }

    stop() {
        this.isRunning = false;
    }

    animate() {
        if (!this.isRunning) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Update and draw particles
        this.particles.forEach(particle => {
            particle.update();
            particle.draw(this.ctx);
        });

        // Draw connections
        this.drawConnections();

        requestAnimationFrame(() => this.animate());
    }

    drawConnections() {
        const maxDistance = 100;

        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);

                if (distance < maxDistance) {
                    const opacity = (1 - distance / maxDistance) * 0.2;
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.strokeStyle = `rgba(30, 58, 95, ${opacity})`;
                    this.ctx.lineWidth = 1;
                    this.ctx.stroke();
                }
            }
        }
    }
}

// ============================================================================
// NETWORK GRAPH
// ============================================================================

class NetworkGraph {
    constructor(canvas, nodeCount) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.nodes = [];
        this.edges = [];
        this.isRunning = false;
        this.activeNodeIndex = -1;

        // Set canvas size
        this.resize();
        window.addEventListener('resize', () => this.resize());

        // Create nodes in a circle
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;
        const radius = Math.min(this.canvas.width, this.canvas.height) * 0.3;

        for (let i = 0; i < nodeCount; i++) {
            const angle = (i / nodeCount) * Math.PI * 2 - Math.PI / 2;
            this.nodes.push({
                x: centerX + Math.cos(angle) * radius,
                y: centerY + Math.sin(angle) * radius,
                radius: 8,
                active: false,
                complete: false
            });
        }

        // Create edges between nodes
        for (let i = 0; i < nodeCount; i++) {
            for (let j = i + 1; j < nodeCount; j++) {
                this.edges.push({ from: i, to: j, opacity: 0 });
            }
        }
    }

    resize() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.offsetWidth;
        this.canvas.height = container.offsetHeight;
    }

    start() {
        this.isRunning = true;
        this.animate();
    }

    stop() {
        this.isRunning = false;
    }

    setActiveNode(index) {
        this.activeNodeIndex = index;
        if (index >= 0 && index < this.nodes.length) {
            this.nodes[index].active = true;

            // Activate edges connected to this node
            this.edges.forEach(edge => {
                if (edge.from === index || edge.to === index) {
                    edge.opacity = 0.6;
                }
            });
        }
    }

    setCompleteNode(index) {
        if (index >= 0 && index < this.nodes.length) {
            this.nodes[index].active = false;
            this.nodes[index].complete = true;
        }
    }

    animate() {
        if (!this.isRunning) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw edges
        this.edges.forEach(edge => {
            if (edge.opacity > 0) {
                const from = this.nodes[edge.from];
                const to = this.nodes[edge.to];

                this.ctx.beginPath();
                this.ctx.moveTo(from.x, from.y);
                this.ctx.lineTo(to.x, to.y);
                this.ctx.strokeStyle = `rgba(30, 58, 95, ${edge.opacity})`;
                this.ctx.lineWidth = 2;
                this.ctx.stroke();

                // Fade out edges
                edge.opacity *= 0.98;
            }
        });

        // Draw nodes
        this.nodes.forEach((node, i) => {
            this.ctx.beginPath();
            this.ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);

            if (node.complete) {
                this.ctx.fillStyle = '#059669';
            } else if (node.active) {
                this.ctx.fillStyle = '#1e3a5f';
                // Pulse effect for active node
                const pulseRadius = node.radius + Math.sin(Date.now() / 200) * 3;
                this.ctx.beginPath();
                this.ctx.arc(node.x, node.y, pulseRadius, 0, Math.PI * 2);
                this.ctx.strokeStyle = 'rgba(30, 58, 95, 0.3)';
                this.ctx.lineWidth = 2;
                this.ctx.stroke();
            } else {
                this.ctx.fillStyle = '#cbd5e1';
            }

            this.ctx.fill();
        });

        requestAnimationFrame(() => this.animate());
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeTicker();
    initializeFrameworks();
    initializeDemoButtons();
    initializeAssessment();
    initializeTabs();
    initializeExport();
    updateAssessmentButton();
});

// ============================================================================
// TICKER ANIMATION
// ============================================================================

function initializeTicker() {
    const fines = [
        '🚨 Recent fine: GDPR Meta €225M penalty',
        '⚠️ SOX violation: $180M Wells Fargo fine',
        '🔴 EU AI Act: €35M maximum penalty',
        '💰 GDPR Amazon: €746M fine (2021)',
        '🏢 SOX Theranos: $500K penalty + criminal charges'
    ];

    let index = 0;
    const tickerContent = document.getElementById('ticker-content');

    setInterval(() => {
        tickerContent.classList.add('fade');

        setTimeout(() => {
            index = (index + 1) % fines.length;
            tickerContent.textContent = fines[index];
            tickerContent.classList.remove('fade');
        }, 500);
    }, 3000);
}

// ============================================================================
// FRAMEWORK SELECTION
// ============================================================================

function initializeFrameworks() {
    const cards = document.querySelectorAll('.framework-card');

    cards.forEach(card => {
        card.addEventListener('click', () => {
            const framework = card.dataset.framework;

            if (card.classList.contains('selected')) {
                if (selectedFrameworks.length > 1) {
                    card.classList.remove('selected');
                    card.querySelector('.framework-checkbox').textContent = '';
                    selectedFrameworks = selectedFrameworks.filter(f => f !== framework);
                }
            } else {
                card.classList.add('selected');
                card.querySelector('.framework-checkbox').textContent = '✓';
                selectedFrameworks.push(framework);
            }

            updateAssessmentButton();
        });
    });
}

// ============================================================================
// DEMO SCENARIOS
// ============================================================================

function initializeDemoButtons() {
    document.getElementById('test-gdpr').addEventListener('click', () => {
        loadDemoScenario('gdpr_hiring');
    });

    document.getElementById('test-sox').addEventListener('click', () => {
        loadDemoScenario('sox_financial');
    });

    document.getElementById('test-euai').addEventListener('click', () => {
        loadDemoScenario('euai_biometric');
    });

    // Enable assessment button on text input
    document.getElementById('system-description').addEventListener('input', (e) => {
        updateAssessmentButton();
    });
}

function updateAssessmentButton() {
    const description = document.getElementById('system-description').value.trim();
    const button = document.getElementById('run-assessment');
    button.disabled = !description || selectedFrameworks.length === 0;
}

// ============================================================================
// ASSESSMENT
// ============================================================================

function initializeAssessment() {
    document.getElementById('run-assessment').addEventListener('click', runAssessment);
    document.getElementById('view-results-btn').addEventListener('click', showResults);
    document.getElementById('new-scan').addEventListener('click', newScan);
}

async function runAssessment() {
    const description = document.getElementById('system-description').value.trim();

    if (!description) return;

    // Show processing section
    showSection('processing-section');

    // Setup judges list
    setupJudgesList();

    // Initialize canvas animations
    initializeProcessingAnimations();

    try {
        // Call API
        const response = await fetch(`${API_BASE}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                description: description,
                frameworks: selectedFrameworks
            })
        });

        if (!response.ok) {
            throw new Error('Analysis failed');
        }

        analysisResults = await response.json();

        // Animate judges completion
        await animateJudgesCompletion();

        // Stop animations
        stopProcessingAnimations();

        // Show victory screen
        showVictory();

    } catch (error) {
        console.error('Assessment error:', error);
        alert('Assessment failed. Please try again.');
        stopProcessingAnimations();
        showSection('scan-section');
    }
}

function initializeProcessingAnimations() {
    const particleCanvas = document.getElementById('particle-canvas');
    const networkCanvas = document.getElementById('network-canvas');
    const judgeItems = document.querySelectorAll('.judge-item');

    // Initialize particle system
    if (particleCanvas) {
        particleSystem = new ParticleSystem(particleCanvas, 120);
        particleSystem.start();
    }

    // Initialize network graph
    if (networkCanvas && judgeItems.length > 0) {
        networkGraph = new NetworkGraph(networkCanvas, judgeItems.length);
        networkGraph.start();
    }
}

function stopProcessingAnimations() {
    if (particleSystem) {
        particleSystem.stop();
        particleSystem = null;
    }
    if (networkGraph) {
        networkGraph.stop();
        networkGraph = null;
    }
}

function setupJudgesList() {
    const judgesList = document.getElementById('judges-list');
    const judges = [];

    if (selectedFrameworks.includes('gdpr')) {
        judges.push(
            { icon: '🇪🇺', name: 'GDPR Article 22 - Automated Decisions' },
            { icon: '🇪🇺', name: 'GDPR Article 17 - Right to Erasure' },
            { icon: '🇪🇺', name: 'GDPR Article 32 - Security' }
        );
    }

    if (selectedFrameworks.includes('sox')) {
        judges.push(
            { icon: '💼', name: 'SOX Section 404 - Internal Controls' },
            { icon: '💼', name: 'SOX Section 302 - Corporate Responsibility' },
            { icon: '💼', name: 'SOX Audit Trail Requirements' }
        );
    }

    if (selectedFrameworks.includes('euai')) {
        judges.push(
            { icon: '🤖', name: 'EU AI Act - High-Risk Systems' },
            { icon: '🤖', name: 'EU AI Act - Prohibited Practices' },
            { icon: '🤖', name: 'EU AI Act - Transparency' }
        );
    }

    judgesList.innerHTML = judges.map((judge, i) => `
        <div class="judge-item" data-index="${i}">
            <span class="judge-icon">${judge.icon}</span>
            <span class="judge-name">${judge.name}</span>
            <span class="judge-status">⏳</span>
        </div>
    `).join('');
}

async function animateJudgesCompletion() {
    const items = document.querySelectorAll('.judge-item');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    for (let i = 0; i < items.length; i++) {
        const item = items[i];

        // Mark as active
        item.classList.add('active');

        // Update network graph
        if (networkGraph) {
            networkGraph.setActiveNode(i);
        }

        // Simulate processing with variable timing
        await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 600));

        // Mark as complete
        item.classList.remove('active');
        item.classList.add('complete');
        item.querySelector('.judge-status').textContent = '✓';

        // Update network graph
        if (networkGraph) {
            networkGraph.setCompleteNode(i);
        }

        // Update progress
        const percent = Math.round(((i + 1) / items.length) * 100);
        progressFill.style.width = percent + '%';
        progressText.textContent = percent + '% Complete';

        // Small delay between judges
        await new Promise(resolve => setTimeout(resolve, 200));
    }
}

function showVictory() {
    showSection('victory-section');

    // Trigger confetti
    confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.6 }
    });

    // Populate victory metrics
    document.getElementById('victory-violations').textContent = analysisResults.violations.length;
    document.getElementById('victory-frameworks').textContent = analysisResults.frameworks_analyzed.length;
    document.getElementById('victory-risk').textContent = analysisResults.risk_score;
}

function showResults() {
    showSection('results-section');
    populateDashboard();
    renderCharts();
}

function newScan() {
    analysisResults = null;
    document.getElementById('system-description').value = '';
    selectedFrameworks = ['gdpr'];

    // Reset framework cards
    document.querySelectorAll('.framework-card').forEach(card => {
        const framework = card.dataset.framework;
        if (framework === 'gdpr') {
            card.classList.add('selected');
            card.querySelector('.framework-checkbox').textContent = '✓';
        } else {
            card.classList.remove('selected');
            card.querySelector('.framework-checkbox').textContent = '';
        }
    });

    showSection('scan-section');
    updateAssessmentButton();
}

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.getElementById(sectionId).classList.add('active');
}

// ============================================================================
// DASHBOARD
// ============================================================================

function populateDashboard() {
    if (!analysisResults) return;

    const { violations, risk_score } = analysisResults;

    // Count priorities
    const p0 = violations.filter(v => v.priority === 'P0').length;
    const p1 = violations.filter(v => v.priority === 'P1').length;
    const p2 = violations.filter(v => v.priority === 'P2').length;

    // Update metrics
    document.getElementById('dashboard-risk').textContent = risk_score;
    document.getElementById('dashboard-total').textContent = violations.length;
    document.getElementById('dashboard-p0').textContent = p0;
    document.getElementById('dashboard-p1').textContent = p1;

    // Render risk gauge
    renderRiskGauge(risk_score);

    // Populate Fix Plan tab
    populateFixPlan();

    // Populate Citations tab
    populateCitations();
}

function renderRiskGauge(score) {
    const canvas = document.getElementById('risk-gauge');
    const ctx = canvas.getContext('2d');

    // Destroy existing chart if any
    if (charts.riskGauge) {
        charts.riskGauge.destroy();
    }

    charts.riskGauge = new Chart(ctx, {
        type: 'doughnut',
        data: {
            datasets: [{
                data: [score, 100 - score],
                backgroundColor: [
                    score <= 25 ? '#059669' :
                    score <= 50 ? '#d97706' :
                    score <= 75 ? '#e67e22' : '#dc2626',
                    '#e2e8f0'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            cutout: '75%',
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            }
        }
    });
}

function renderCharts() {
    if (!analysisResults) return;

    const { violations } = analysisResults;

    // Severity Chart
    renderSeverityChart(violations);

    // Framework Chart
    renderFrameworkChart(violations);
}

function renderSeverityChart(violations) {
    const canvas = document.getElementById('severity-chart');
    const ctx = canvas.getContext('2d');

    if (charts.severity) {
        charts.severity.destroy();
    }

    const severityCounts = {
        'CRITICAL': violations.filter(v => v.severity === 'CRITICAL').length,
        'MAJOR': violations.filter(v => v.severity === 'MAJOR').length,
        'MINOR': violations.filter(v => v.severity === 'MINOR').length
    };

    charts.severity = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(severityCounts),
            datasets: [{
                data: Object.values(severityCounts),
                backgroundColor: ['#dc2626', '#d97706', '#059669'],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12, weight: '600' }
                    }
                }
            }
        }
    });
}

function renderFrameworkChart(violations) {
    const canvas = document.getElementById('framework-chart');
    const ctx = canvas.getContext('2d');

    if (charts.framework) {
        charts.framework.destroy();
    }

    const frameworkCounts = {};
    violations.forEach(v => {
        const fw = v.framework || 'Unknown';
        frameworkCounts[fw] = (frameworkCounts[fw] || 0) + 1;
    });

    charts.framework = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(frameworkCounts),
            datasets: [{
                label: 'Violations',
                data: Object.values(frameworkCounts),
                backgroundColor: '#1e3a5f',
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function populateFixPlan() {
    if (!analysisResults) return;

    const { violations } = analysisResults;

    const technical = violations
        .filter(v => v.complexity === 'High' || v.complexity === 'Medium')
        .map(v => ({
            title: v.article_violated,
            desc: v.engineering_scope || 'Technical implementation required',
            priority: v.priority
        }));

    const business = violations
        .filter(v => v.complexity === 'Low')
        .map(v => ({
            title: v.article_violated,
            desc: 'Process and policy updates required',
            priority: v.priority
        }));

    document.getElementById('technical-changes').innerHTML = technical.length ?
        technical.map(item => `
            <div class="fix-item">
                <div class="fix-item-title">${item.title} <span class="priority-badge badge-${item.priority.toLowerCase()}">${item.priority}</span></div>
                <div class="fix-item-desc">${item.desc}</div>
            </div>
        `).join('') :
        '<p style="color: #64748b;">No major technical changes required.</p>';

    document.getElementById('business-changes').innerHTML = business.length ?
        business.map(item => `
            <div class="fix-item">
                <div class="fix-item-title">${item.title} <span class="priority-badge badge-${item.priority.toLowerCase()}">${item.priority}</span></div>
                <div class="fix-item-desc">${item.desc}</div>
            </div>
        `).join('') :
        '<p style="color: #64748b;">No major process changes required.</p>';
}

function populateCitations() {
    if (!analysisResults) return;

    const { violations } = analysisResults;
    const violationsList = document.getElementById('violations-list');

    if (violations.length === 0) {
        violationsList.innerHTML = '<p style="text-align: center; color: #64748b; padding: 40px;">No violations detected. Your system appears compliant!</p>';
        return;
    }

    // Sort by priority
    const sorted = violations.sort((a, b) => {
        const order = { 'P0': 0, 'P1': 1, 'P2': 2 };
        return order[a.priority] - order[b.priority];
    });

    violationsList.innerHTML = sorted.map((v, i) => `
        <div class="violation-card" data-index="${i}">
            <div class="violation-header" onclick="toggleViolation(${i})">
                <div class="violation-title-section">
                    <div class="violation-framework">${v.framework}</div>
                    <div class="violation-title">${v.article_violated}</div>
                    <div class="violation-meta">
                        <span class="priority-badge badge-${v.priority.toLowerCase()}">${v.priority}</span>
                        <span class="priority-badge" style="background: #f1f5f9; color: #64748b;">${v.complexity} Complexity</span>
                        <span class="priority-badge" style="background: #f1f5f9; color: #64748b;">${v.timeline}</span>
                        <span class="priority-badge" style="background: #f1f5f9; color: #64748b;">${Math.round(v.confidence * 100)}% confidence</span>
                    </div>
                </div>
                <div style="font-size: 24px; color: #64748b;">▼</div>
            </div>
            <div class="violation-body">
                <div class="violation-section">
                    <h4>Evidence</h4>
                    <div class="evidence-box">"${v.evidence_quote}"</div>
                </div>

                <div class="violation-section">
                    <h4>Engineering Scope</h4>
                    <p>${v.engineering_scope || 'Not specified'}</p>
                </div>

                <div class="violation-section">
                    <h4>Remediation Steps</h4>
                    <ul class="remediation-list">
                        ${v.remediation_steps.map(step => `<li>${step}</li>`).join('')}
                    </ul>
                </div>

                <div class="violation-section">
                    <h4>Risk Factors</h4>
                    <ul class="risk-list">
                        ${(v.risk_factors || []).map(risk => `<li>${risk}</li>`).join('') || '<li>No specific risk factors identified</li>'}
                    </ul>
                </div>

                ${v.dependencies && v.dependencies.length ? `
                    <div class="violation-section">
                        <h4>Dependencies</h4>
                        <ul class="remediation-list">
                            ${v.dependencies.map(dep => `<li>${dep}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function toggleViolation(index) {
    const card = document.querySelector(`.violation-card[data-index="${index}"]`);
    card.classList.toggle('expanded');
}

// Make toggleViolation available globally
window.toggleViolation = toggleViolation;

// ============================================================================
// TABS
// ============================================================================

function initializeTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;

            // Update active tab
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update active content
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(`tab-${tabName}`).classList.add('active');
        });
    });
}

// ============================================================================
// EXPORT
// ============================================================================

function initializeExport() {
    document.getElementById('export-pdf').addEventListener('click', exportPDF);
    document.getElementById('export-csv').addEventListener('click', exportCSV);
}

async function exportPDF() {
    if (!analysisResults || !analysisResults.analysis_id) {
        alert('No analysis results to export');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/export/pdf/${analysisResults.analysis_id}`);

        if (!response.ok) {
            throw new Error('PDF export failed');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sovereign-compliance-report-${new Date().toISOString().split('T')[0]}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('PDF export error:', error);
        alert('PDF export failed. Please try again.');
    }
}

async function exportCSV() {
    if (!analysisResults || !analysisResults.analysis_id) {
        alert('No analysis results to export');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/export/csv/${analysisResults.analysis_id}`);

        if (!response.ok) {
            throw new Error('CSV export failed');
        }

        const text = await response.text();
        const blob = new Blob([text], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sovereign-violations-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        console.error('CSV export error:', error);
        alert('CSV export failed. Please try again.');
    }
}
