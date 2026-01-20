// Map dimensions
const width = document.getElementById('map').clientWidth;
const height = document.getElementById('map').clientHeight;

// Create SVG
const svg = d3.select("#map")
    .append("svg")
    .attr("width", width)
    .attr("height", height);

const g = svg.append("g");

// Zoom behavior
const zoom = d3.zoom()
    .scaleExtent([1, 8])
    .on("zoom", (event) => {
        g.attr("transform", event.transform);
    });

svg.call(zoom);

// Projection for India
const projection = d3.geoMercator()
    .center([78.9629, 22.5937])
    .scale(1000)
    .translate([width / 2, height / 2]);

const path = d3.geoPath().projection(projection);

// Tooltip
const tooltip = d3.select("#tooltip");

// Store district data
let districtDataCache = {};
let allDistrictAggregates = {};

// Chart instances
let enrolmentChart = null;
let updateChart = null;
let ageChart = null;

// Typology colors - Pastel palette
const typologyColors = {
    'Stable & Saturated': '#86efac',  // Pastel green
    'Volatile': '#fde047',             // Pastel yellow
    'Growth-focused': '#93c5fd',       // Pastel blue
    'Under-maintained': '#fca5a5',     // Pastel red
    'Balanced': '#c4b5fd',             // Pastel purple
    'Unknown': '#d1d5db'               // Pastel gray
};

// Color scale for districts based on typology
function getDistrictColor(typology) {
    return typologyColors[typology] || '#6b7280';
}

// Create a group for labels
const labelGroup = g.append("g").attr("class", "labels");

// Load all district aggregates FIRST, then load GeoJSON
fetch('/api/districts/all')
    .then(response => response.json())
    .then(data => {
        allDistrictAggregates = data;
        console.log("Loaded district aggregates for", Object.keys(data).length, "districts");
        
        // Now load and render GeoJSON with the district data available
        return d3.json("/api/geojson");
    })
    .then(function (data) {
        // Remove loading message
        d3.select(".loading").remove();

        // Draw districts
        g.selectAll("path")
            .data(data.features)
            .enter()
            .append("path")
            .attr("d", path)
            .attr("class", "district")
            .attr("fill", d => {
                const districtName = (d.properties.NAME_2 || "").toLowerCase().trim();
                const districtData = allDistrictAggregates[districtName];
                if (districtData) {
                    return getDistrictColor(districtData.district_typology);
                }
                return '#d1d5db';
            })
        .attr("stroke", "#94a3b8")
        .attr("stroke-width", "0.5px")
        .attr("stroke-opacity", "0.8")
        .on("mouseover", function (event, d) {
            const districtName = d.properties.NAME_2 || "Unknown";
            const stateName = d.properties.NAME_1 || "Unknown";

            // Highlight district
            d3.select(this)
                .style("stroke", "#667eea")
                .style("stroke-width", "2px")
                .style("filter", "brightness(1.1) saturate(1.2)");

            // Get centroid for label placement
            const centroid = path.centroid(d);

            // Add text labels on the map
            labelGroup.append("text")
                .attr("class", "district-label")
                .attr("x", centroid[0])
                .attr("y", centroid[1] - 10)
                .attr("text-anchor", "middle")
                .style("font-size", "14px")
                .style("font-weight", "bold")
                .style("fill", "#1e293b")
                .style("pointer-events", "none")
                .style("text-shadow", "1px 1px 3px rgba(255,255,255,0.9), -1px -1px 3px rgba(255,255,255,0.9)")
                .text(districtName);

            labelGroup.append("text")
                .attr("class", "state-label")
                .attr("x", centroid[0])
                .attr("y", centroid[1] + 8)
                .attr("text-anchor", "middle")
                .style("font-size", "11px")
                .style("fill", "#667eea")
                .style("pointer-events", "none")
                .style("text-shadow", "1px 1px 3px rgba(255,255,255,0.9)")
                .text(stateName);

            // Show summarized tooltip with key metrics
            const districtKey = districtName.toLowerCase().trim();
            const cachedData = allDistrictAggregates[districtKey];

            let tooltipContent = `
                        <h4>${districtName}</h4>
                        <div class="tooltip-row">
                            <span class="tooltip-label">State:</span>
                            <span class="tooltip-value">${stateName}</span>
                        </div>
                    `;

            if (cachedData) {
                tooltipContent += `
                            <div class="tooltip-row">
                                <span class="tooltip-label">Typology:</span>
                                <span class="tooltip-value">${cachedData.district_typology}</span>
                            </div>
                            <div class="tooltip-row">
                                <span class="tooltip-label">Enrolments:</span>
                                <span class="tooltip-value">${formatNumber(cachedData.total_enrolments)}</span>
                            </div>
                            <div class="tooltip-row">
                                <span class="tooltip-label">Demo Updates:</span>
                                <span class="tooltip-value">${formatNumber(cachedData.total_demo_updates)}</span>
                            </div>
                            <div class="tooltip-row">
                                <span class="tooltip-label">Bio Updates:</span>
                                <span class="tooltip-value">${formatNumber(cachedData.total_bio_updates)}</span>
                            </div>
                            <div class="tooltip-row">
                                <span class="tooltip-label">Volatility:</span>
                                <span class="tooltip-value">${cachedData.identity_volatility.toFixed(3)}</span>
                            </div>
                            <div class="tooltip-hint">Click for detailed analytics</div>
                        `;
            } else {
                tooltipContent += `
                            <div class="tooltip-hint">No data available</div>
                        `;
            }

            tooltip.html(tooltipContent)
                .classed("visible", true)
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 15) + "px");
        })
        .on("mousemove", function (event) {
            tooltip
                .style("left", (event.pageX + 15) + "px")
                .style("top", (event.pageY - 15) + "px");
        })
        .on("mouseout", function () {
            d3.select(this)
                .style("stroke", "#94a3b8")
                .style("stroke-width", "0.5px")
                .style("filter", null);

            // Remove labels
            labelGroup.selectAll(".district-label").remove();
            labelGroup.selectAll(".state-label").remove();

            tooltip.classed("visible", false);
        })
        .on("click", function (event, d) {
            const districtName = d.properties.NAME_2 || "Unknown";
            
            // Load full district data for side panel on click
            loadDistrictAnalytics(districtName);
            
            // Visual feedback for selected district
            g.selectAll("path.district").classed("selected", false);
            d3.select(this).classed("selected", true);
        });

    console.log("Map loaded successfully with", data.features.length, "districts");

}).catch(function (error) {
    console.error("Error loading map/data:", error);
    d3.select(".loading").html("Error loading map data");
});

// Load district analytics for side panel
function loadDistrictAnalytics(districtName) {
    const infoPanel = document.getElementById('district-info');

    // Show loading state
    infoPanel.innerHTML = `
                <div class="panel-loading">
                    <div class="spinner"></div>
                    <p>Loading analytics for ${districtName}...</p>
                </div>
            `;

    fetch(`/api/district/${encodeURIComponent(districtName)}`)
        .then(response => response.json())
        .then(data => {
            if (data.total_enrolments === 0 && data.state === 'Unknown') {
                infoPanel.innerHTML = `
                            <div class="no-data">
                                <p>No data available for <strong>${districtName}</strong></p>
                                <p style="font-size: 11px; margin-top: 10px;">This district may not have matching records in the dataset</p>
                            </div>
                        `;
                return;
            }
            renderDistrictPanel(data);
        })
        .catch(error => {
            console.error("Error loading district data:", error);
            infoPanel.innerHTML = `
                        <div class="no-data">
                            <p>Error loading data for ${districtName}</p>
                        </div>
                    `;
        });
}

// Render the district analytics panel
function renderDistrictPanel(data) {
    const infoPanel = document.getElementById('district-info');

    // Determine typology class
    const typologyClass = 'typology-' + data.district_typology.toLowerCase().replace(/[^a-z]/g, '').replace('saturated', 'stable');

    // Generate insight based on data
    const insight = generateInsight(data);

    infoPanel.innerHTML = `
                <div class="data-card">
                    <h3>${data.state}</h3>
                    <div class="value">${data.district}</div>
                    <span class="typology-badge ${typologyClass}">${data.district_typology}</span>
                </div>

                <div class="insight-box">
                    <div class="title"><i class="fas fa-clipboard-list"></i> District Insight</div>
                    ${insight}
                </div>

                <div class="section-divider">
                    <h4 style="color: #bb86fc; font-size: 12px; text-transform: uppercase;">Enrolment Overview</h4>
                </div>

                <div class="stats-grid">
                    <div class="stat-item" data-tooltip="Total number of new Aadhaar enrolments in this district. High: Active enrolment/expansion. Low: Saturated or under-served area.">
                        <div class="label">Total Enrolments <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${formatNumber(data.total_enrolments)}</div>
                    </div>
                    <div class="stat-item" data-tooltip="Percentage of enrolments from adults (18+). High: Late inclusion or migration. Low: Child-focused registration activity.">
                        <div class="label">Adult Share <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${data.adult_enrolment_share.toFixed(1)}%</div>
                    </div>
                    <div class="stat-item" data-tooltip="Total demographic updates (name, address, DOB changes). High: Administrative churn or migration pressure. Low: Stable identity records.">
                        <div class="label">Demo Updates <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${formatNumber(data.total_demo_updates)}</div>
                    </div>
                    <div class="stat-item" data-tooltip="Total biometric updates (fingerprint, iris refreshes). High: Active lifecycle maintenance. Low: Potential future reliability risks.">
                        <div class="label">Bio Updates <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${formatNumber(data.total_bio_updates)}</div>
                    </div>
                </div>

                <div class="chart-container">
                    <h4><i class="fas fa-chart-pie"></i> Age Distribution (Enrolments)</h4>
                    <div class="chart-wrapper">
                        <canvas id="ageChart"></canvas>
                    </div>
                </div>

                <div class="section-divider">
                    <h4 style="color: #475569; font-size: 12px; text-transform: uppercase;">Derived Metrics</h4>
                </div>

                <div class="metric-bar" data-tooltip="Ratio of demographic updates to enrolments. Measures how often identity records change. High (>0.5): Frequent changes, migration pressure. Low (<0.1): Stable records.">
                    <div class="label">
                        <span>Identity Volatility <i class="fas fa-info-circle info-icon"></i></span>
                        <span>${data.identity_volatility.toFixed(3)}</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: ${Math.min(data.identity_volatility * 100, 100)}%; background: linear-gradient(90deg, #fde68a, #fca5a5);"></div>
                    </div>
                </div>

                <div class="metric-bar" data-tooltip="Adult biometric updates relative to adult enrolments. High (>70%): Active biometric maintenance. Low (<30%): Potential lifecycle gaps, aging biometrics.">
                    <div class="label">
                        <span>Adult Bio Compliance <i class="fas fa-info-circle info-icon"></i></span>
                        <span>${data.adult_bio_compliance.toFixed(1)}%</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: ${Math.min(data.adult_bio_compliance, 100)}%; background: linear-gradient(90deg, #a7f3d0, #93c5fd);"></div>
                    </div>
                </div>

                <div class="metric-bar" data-tooltip="Child biometric updates relative to child enrolments. High: Active child biometric refreshes. Low: May need outreach for child biometric updates.">
                    <div class="label">
                        <span>Child Bio Compliance <i class="fas fa-info-circle info-icon"></i></span>
                        <span>${data.child_bio_compliance.toFixed(1)}%</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: ${Math.min(data.child_bio_compliance, 100)}%; background: linear-gradient(90deg, #c4b5fd, #f9a8d4);"></div>
                    </div>
                </div>

                <div class="metric-bar" data-tooltip="Ratio of biometric to demographic updates. Measures if bio updates keep pace with demo changes. High (>1): Bio updates exceed demo changes. Low (<0.5): Maintenance imbalance risk.">
                    <div class="label">
                        <span>Lifecycle Integrity <i class="fas fa-info-circle info-icon"></i></span>
                        <span>${data.lifecycle_integrity.toFixed(3)}</span>
                    </div>
                    <div class="bar-bg">
                        <div class="bar-fill" style="width: ${Math.min(data.lifecycle_integrity * 100, 100)}%; background: linear-gradient(90deg, #a5f3fc, #a7f3d0);"></div>
                    </div>
                </div>

                <div class="chart-container">
                    <h4><i class="fas fa-chart-line"></i> Updates Comparison</h4>
                    <div class="chart-wrapper">
                        <canvas id="updateChart"></canvas>
                    </div>
                </div>

                ${data.time_series && data.time_series.enrolment && data.time_series.enrolment.months.length > 0 ? `
                <div class="chart-container">
                    <h4><i class="fas fa-calendar-alt"></i> Monthly Trends</h4>
                    <div class="chart-wrapper mini-chart">
                        <canvas id="trendChart"></canvas>
                    </div>
                </div>
                ` : ''}

                <div class="section-divider">
                    <h4 style="color: #bb86fc; font-size: 12px; text-transform: uppercase;">Raw Numbers</h4>
                </div>

                <div class="stats-grid">
                    <div class="stat-item" data-tooltip="Enrolments of children aged 0-5 years. High values indicate strong infant/toddler registration. Low values may suggest outreach gaps for newborns.">
                        <div class="label">Enrol 0-5 <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${formatNumber(data.enrol_0_5)}</div>
                    </div>
                    <div class="stat-item" data-tooltip="Enrolments of children aged 5-17 years. High values indicate strong school-age registration. Low values may indicate delayed child enrolment.">
                        <div class="label">Enrol 5-17 <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${formatNumber(data.enrol_5_17)}</div>
                    </div>
                    <div class="stat-item" data-tooltip="New enrolments for adults 18+ years. High values suggest significant adult population without prior Aadhaar. Low values indicate mature coverage.">
                        <div class="label">Enrol 18+ <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${formatNumber(data.enrol_18_plus)}</div>
                    </div>
                    <div class="stat-item" data-tooltip="Demographic updates for adults 18+. High values indicate active address/name corrections. Low values suggest stable demographic records.">
                        <div class="label">Demo 18+ <i class="fas fa-info-circle info-icon"></i></div>
                        <div class="value">${formatNumber(data.demo_18_plus)}</div>
                    </div>
                </div>
            `;

    // Render charts
    renderAgeChart(data);
    renderUpdateChart(data);
    if (data.time_series && data.time_series.enrolment && data.time_series.enrolment.months.length > 0) {
        renderTrendChart(data);
    }
}

// Generate insight text based on data
function generateInsight(data) {
    let insights = [];

    if (data.identity_volatility > 0.5) {
        insights.push("This district shows <strong>high identity volatility</strong>, suggesting frequent demographic updates relative to new enrolments. This may indicate migration pressure or administrative churn.");
    } else if (data.identity_volatility < 0.1) {
        insights.push("This district has <strong>low identity volatility</strong>, suggesting stable identity records with minimal updates.");
    }

    if (data.adult_bio_compliance < 30) {
        insights.push("Adult biometric compliance appears <strong>relatively low</strong>, which may suggest potential lifecycle maintenance gaps.");
    } else if (data.adult_bio_compliance > 70) {
        insights.push("Adult biometric compliance is <strong>relatively high</strong>, indicating active biometric update activity.");
    }

    if (data.adult_enrolment_share > 70) {
        insights.push("Enrolments are <strong>adult-dominant</strong>, which may indicate late inclusion or migration patterns.");
    } else if (data.child_enrolment_share > 60) {
        insights.push("Enrolments show <strong>higher child share</strong>, possibly reflecting targeted child registration outreach.");
    }

    if (data.maintenance_imbalance > 0.5) {
        insights.push("There appears to be a <strong>maintenance imbalance</strong> — demographic records are changing but biometrics may not be refreshed proportionally.");
    }

    if (insights.length === 0) {
        insights.push("This district shows <strong>balanced patterns</strong> across enrolment, demographic, and biometric metrics.");
    }

    return insights.join('<br><br>');
}

// Render age distribution chart
function renderAgeChart(data) {
    const ctx = document.getElementById('ageChart');
    if (!ctx) return;

    if (ageChart) ageChart.destroy();

    ageChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['0-5 Years', '5-17 Years', '18+ Years'],
            datasets: [{
                data: [data.enrol_0_5, data.enrol_5_17, data.enrol_18_plus],
                backgroundColor: ['#f9a8d4', '#c4b5fd', '#93c5fd'],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        color: '#475569',
                        font: { size: 10 },
                        boxWidth: 12
                    }
                }
            }
        }
    });
}

// Render update comparison chart
function renderUpdateChart(data) {
    const ctx = document.getElementById('updateChart');
    if (!ctx) return;

    if (updateChart) updateChart.destroy();

    updateChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Children', 'Adults'],
            datasets: [
                {
                    label: 'Demographic',
                    data: [data.demo_5_17, data.demo_18_plus],
                    backgroundColor: '#fde68a',
                    borderColor: '#fbbf24',
                    borderWidth: 1
                },
                {
                    label: 'Biometric',
                    data: [data.bio_5_17, data.bio_18_plus],
                    backgroundColor: '#a7f3d0',
                    borderColor: '#34d399',
                    borderWidth: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#475569',
                        font: { size: 10 },
                        boxWidth: 12
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#64748b', font: { size: 10 } },
                    grid: { color: '#e2e8f0' }
                },
                y: {
                    ticks: { color: '#64748b', font: { size: 10 } },
                    grid: { color: '#e2e8f0' }
                }
            }
        }
    });
}

// Render trend chart
function renderTrendChart(data) {
    const ctx = document.getElementById('trendChart');
    if (!ctx) return;

    const ts = data.time_series;
    const months = ts.enrolment?.months || [];

    if (enrolmentChart) enrolmentChart.destroy();

    enrolmentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months.map(m => m.substring(5)), // Show only month part
            datasets: [
                {
                    label: 'Enrolments',
                    data: ts.enrolment?.total || [],
                    borderColor: '#818cf8',
                    backgroundColor: 'rgba(129, 140, 248, 0.2)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    ticks: { color: '#64748b', font: { size: 8 } },
                    grid: { display: false }
                },
                y: {
                    ticks: { color: '#64748b', font: { size: 8 } },
                    grid: { color: '#e2e8f0' }
                }
            }
        }
    });
}

// Format number helper
function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(2) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toString();
}

// Reset zoom function
function resetZoom() {
    svg.transition()
        .duration(750)
        .call(zoom.transform, d3.zoomIdentity);
}

// Toggle legend
function toggleLegend() {
    const legend = document.getElementById('legend');
    legend.style.display = legend.style.display === 'none' ? 'block' : 'none';
}

// Handle window resize
window.addEventListener('resize', () => {
    location.reload();
});